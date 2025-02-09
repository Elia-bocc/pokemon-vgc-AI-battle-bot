import math
from typing import Any, List, Union
from copy import deepcopy

import numpy as np
import random

from vgc.behaviour import BattlePolicy
from vgc.datatypes.Types import PkmStatus, WeatherCondition, PkmStat
from vgc.datatypes.Objects import GameState, PkmTeam, PkmType, Pkm, PkmMove, PkmStatus
from vgc.datatypes.Constants import DEFAULT_N_ACTIONS, TYPE_CHART_MULTIPLIER
from vgc.competition.StandardPkmMoves import STANDARD_MOVE_ROSTER

  
def match_up_eval(my_pkm_type: PkmType,
      opp_pkm_type: PkmType,
      my_moves_type: List[PkmType],
      opp_moves_type: List[PkmType]
  ) -> float:
  # determine defensive match up
  defensive_match_up = 0.
  for mtype in opp_moves_type:
    if mtype == opp_pkm_type:
      defensive_match_up = max(TYPE_CHART_MULTIPLIER[mtype][my_pkm_type]*1.5, defensive_match_up)
    else:
      defensive_match_up = max(TYPE_CHART_MULTIPLIER[mtype][my_pkm_type], defensive_match_up)
  #print(f'DEFENSIVE MATCH UP: {defensive_match_up}')

  offensive_match_up = 0.
  for mtype in my_moves_type:
    if mtype == opp_pkm_type:
      offensive_match_up = max(TYPE_CHART_MULTIPLIER[mtype][opp_pkm_type]*1.5, offensive_match_up)
    else:
      offensive_match_up = max(TYPE_CHART_MULTIPLIER[mtype][my_pkm_type], offensive_match_up)
  #print(f'OFFENSIVE MATCH UP: {offensive_match_up}')
    
  return offensive_match_up - defensive_match_up


def n_fainted(team: PkmTeam) -> int:
  fainted = 0
  fainted += team.active.hp == 0
  if len(team.party) > 0:
    fainted += team.party[0].hp == 0
  if len(team.party) > 1:
    fainted += team.party[1].hp == 0
  return fainted

def calculate_damage(move: PkmMove, pkm_type: PkmType, opp_pkm_type: PkmType, attack_stage: int, defense_stage: int, weather: WeatherCondition) -> float:
    if move.pp <= 0:
      return 0
    if move.name is None:
      return 0
    move_type: PkmType = move.type
    move_power: float = move.power
    type_rate = TYPE_CHART_MULTIPLIER[move_type][opp_pkm_type]
    if type_rate == 0:
        return 0
    if move.fixed_damage > 0:
        return move.fixed_damage
    stab = 1.5 if move_type == pkm_type else 1.
    if (move_type == PkmType.WATER and weather == WeatherCondition.RAIN) or (
            move_type == PkmType.FIRE and weather == WeatherCondition.SUNNY):
        weather = 1.5
    elif (move_type == PkmType.WATER and weather == WeatherCondition.SUNNY) or (
            move_type == PkmType.FIRE and weather == WeatherCondition.RAIN):
        weather = .5
    else:
        weather = 1.
    stage_level = attack_stage - defense_stage
    stage = (stage_level + 2.) / 2 if stage_level >= 0. else 2. / \
        (np.abs(stage_level) + 2.)
    damage = type_rate * \
        stab * weather * stage * move_power
    return damage

def canAttackFirst(my_team:PkmTeam, opp_team:PkmTeam, opp_active:Pkm) -> int:
    
    speed0 = my_team.stage[PkmStat.SPEED]
    speed1 = opp_team.stage[PkmStat.SPEED]

    opp_might_act_earlier = False
    for opp_poss_act in opp_active.moves:
        if opp_poss_act.priority:
            opp_might_act_earlier = True

    if speed1 > speed0:
        if opp_might_act_earlier:
            return -2
        return -1
    if speed0 > speed1 and not opp_might_act_earlier:
        return 1
    if speed0 > speed1 and opp_might_act_earlier:
        return 0.5
    else:
        return 0

def canDefeat(attack1:int, defense2:int, pkm1:Pkm, pkm2:Pkm, weather:WeatherCondition):
    moves = []
    for i in range(0, len(pkm1.moves)):
        #print('prima del danno')
        damage = calculate_damage(pkm1.moves[i], pkm1.type, pkm2.type, attack1, defense2, weather)
        #print(damage)
        if damage >= pkm2.hp:
          #print('entrato')
          moves.append((pkm1.moves.index(pkm1.moves[i]), damage, pkm1.moves[i].max_pp, pkm1.moves[i].acc, pkm1.moves[i].priority))
    # se ho delle mosse che sconfiggono l'avversario le ordino in modo da avere prima quelle più accurate e con più max_pp
    # il controllo di accuratezza sarà da fare in seguito se occorre
    #print(moves)
    if len(moves)>0:
      moves.sort(reverse=True, key=lambda x : (x[3], x[2]))
    return moves

def calculateDamages(attack1:int, defense2:int, pkm1:Pkm, pkm2:Pkm, weather:WeatherCondition):
  moves = []
  for i in range(0, len(pkm1.moves)):
      damage = calculate_damage(pkm1.moves[i], pkm1.type, pkm2.type, attack1, defense2, weather)
      moves.append((pkm1.moves.index(pkm1.moves[i]), damage, pkm1.moves[i].max_pp, pkm1.moves[i].acc, pkm1.moves[i].priority, pkm1.moves[i].status, pkm1.moves[i].target))
  moves.sort(reverse=True, key=lambda x : (x[3], x[1], x[2]))
  return moves

class GreedyPolicy(BattlePolicy):

  def get_action(self, g: GameState) -> int:
    return self._simple_search(g)

  def _simple_search(self, g: GameState) -> int:

    team0 = g.teams[0]
    team1 = g.teams[1]
    my_active = team0.active
    opp_active = team1.active
    weather = g.weather.condition
    # controllo i match up della mia squadra
    match_up = match_up_eval(my_active.type, opp_active.type, list(map(lambda m: m.type, my_active.moves)), list(map(lambda m: m.type, [move for move in opp_active.moves if move.name != None])))
    pkm1_match_up = match_up_eval(team0.party[0].type, opp_active.type, list(map(lambda m: m.type, team0.party[0].moves)), list(map(lambda m: m.type, [move for move in opp_active.moves if move.name!=None])))
    pkm2_match_up = match_up_eval(team0.party[1].type, opp_active.type, list(map(lambda m: m.type, team0.party[1].moves)), list(map(lambda m: m.type, [move for move in opp_active.moves if move.name!=None])))
    # controllo chi attacca prima
    attack_order = canAttackFirst(team0, team1, team1.active)
    # controllo se riesco a sconfiggere l'avversario con una mossa
    moves = canDefeat(team0.stage[PkmStat.ATTACK], team1.stage[PkmStat.DEFENSE], team0.active, team1.active, weather)
    #print(moves)
    # se posso batterlo 
    if len(moves) > 0:
      # se attacco sicuramente prima allora prendo la prima mossa più accurata con più pp che lo sconfigge
      if attack_order == 1:
        return moves[0][0]
      # se l'avversario ha una mossa prioritaria controllo che non possa sconfiggermi
      elif attack_order == 0.5:
        if calculate_damage([m for m in opp_active.moves if m.priority==True][0], opp_active.type, my_active.type, team1.stage[PkmStat.ATTACK], team0.stage[PkmStat.DEFENSE], weather) < my_active.hp:
          return moves[0][0]
      # se l'avversario è più veloce
      if attack_order <= 0:
        # se ho una mossa prioritaria che lo sconfigge la prendo
        if sum([m[4] for m in moves])>=1:
          return [m[0] for m in moves if m[4] == True][0]
        # se comunque l'avversario non può sconfiggermi con una mossa allora prendo la mia mossa che lo sconfigge
        if len(canDefeat(team1.stage[PkmStat.ATTACK], team0.stage[PkmStat.DEFENSE], team1.active, team0.active, weather))==0:
          return moves[0][0]

    # se l'avversario può battermi con una mossa tento di infliggergli uno status se posso
    if len(canDefeat(team1.stage[PkmStat.ATTACK], team0.stage[PkmStat.DEFENSE], team1.active, team0.active, weather))>0:
      stateMoves = [m for m in my_active.moves if m.target==1 and (m.status==PkmStatus.CONFUSED or m.status==PkmStatus.PARALYZED or m.status==PkmStatus.SLEEP or m.status==PkmStatus.FROZEN)]
      # se ho una qualche mossa di stato
      if len(stateMoves) > 0:
        # guardo se ce n'è una che addormenta o che congela, se si le prendo in ordine altrimenti ne prendo una qualsiasi
        sleep = [my_active.moves.index(m) for m in stateMoves if m.status==PkmStatus.SLEEP]
        ice = [my_active.moves.index(m) for m in stateMoves if m.status==PkmStatus.FROZEN]
        if len(sleep) > 0:
          return sleep[0]
        elif len(ice)>0 and opp_active.type!=PkmType.ICE:
          return ice[0]
        else:
          return my_active.moves.index(stateMoves[0])

    # se non lo batto con una mossa controllo:
    # se sono in una situazione accettabile o ho il team esausto o sono in svantaggio ma non ho cambi migliori allora tengo il pkm in campo 
    if match_up >= 0.5 or n_fainted(team0)==2 or (match_up < 0.5 and not (pkm1_match_up > match_up or pkm2_match_up > match_up)):
      # calcolo i danni delle mie mosse
      damages = calculateDamages(team0.stage[PkmStat.ATTACK], team1.stage[PkmStat.DEFENSE], team0.active, team1.active, weather)
      # controllo se in 3 turni riesco a sconfiggere il nemico
      beatMoves = [] 
      for move in damages:
        if move[1]*math.floor(3*move[3]) > opp_active.hp:
          beatMoves.append(move)
      # se non ho mosse che sconfiggerebbero il nemico in 3 turni controllo se ho delle mosse di stato
      if len(beatMoves) == 0:
        stateMoves = [m for m in damages if m[6]==1 and (m[5]==PkmStatus.CONFUSED or m[5]==PkmStatus.PARALYZED or m[5]==PkmStatus.SLEEP or m[5]==PkmStatus.FROZEN)]
        # se ho una qualche mossa di stato
        if len(stateMoves) > 0:
          # guardo se ce n'è una che addormenta o che congela, se si le prendo in ordine altrimenti ne prendo una qualsiasi
          sleep = [m[0] for m in stateMoves if m[5]==PkmStatus.SLEEP]
          ice = [m[0] for m in stateMoves if m[5]==PkmStatus.FROZEN]
          if len(sleep) > 0:
            return sleep[0]
          elif len(ice)>0 and opp_active.type!=PkmType.ICE:
            return ice[0]
          else:
            return stateMoves[0][0]
        # se non ho nemmeno mosse di stato prendo la mossa più potente che ho rapportata all'accuratezza
        else: 
          damages.sort(reverse=True, key=lambda x : (x[1]*x[3]))
          return damages[0][0]
      # se invece ho almeno una mossa che in 3 turni sconfigge il nemico allora prendo
      else:
        # riordino le beatMoves per prendere quella che fa più danno
        # (anche se le mosse più potenti potrebbero essere poco accurate ma ci va bene perché è già stato considerato)
        beatMoves.sort(reverse=True, key=lambda x : (x[1]))
        return beatMoves[0][0]
                
      # per ora uso un approccio greedy ma è da fare una simulazione di 2-3 turni con tutte le mosse
      #return int(np.argmax([calculate_damage(m, my_active.type, opp_active.type, team0.stage[PkmStat.ATTACK], team1.stage[PkmStat.DEFENSE], weather) for m in my_active.moves]))  
    # altrimenti (comprende il caso in cui il pkm è in svantaggio e ho pkm migliori in squadra) faccio lo switch con il pkm migliore
    else:
      if pkm1_match_up >= pkm2_match_up:
        if not team0.party[0].fainted():
          return 4
        else:
          return 5
      else: 
        if not team0.party[1].fainted():
          return 5
        else:
          return 4

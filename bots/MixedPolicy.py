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

class Node():

  def __init__(self):
    self.action: int = None
    self.gameState: GameState = None
    self.parent: Node = None
    self.depth: int = 0
    self.value: float = 0.

  def __str__(self):
    return f'Node(action: {self.action}, depth: {self.depth}, value: {self.value}, parent: {str(self.parent)})'
  
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

def estimate_move(pkm: Pkm) -> None:
  # controlla se è già presente una mossa del tipo del pokemon
  type_m = sum([move.type==pkm.type for move in pkm.moves if move.name is not None])
  for move_i in range(DEFAULT_N_ACTIONS-2):
    if pkm.moves[move_i].name is None:
      # se non è presente una mossa del tipo del pkm allora ne aggiungo una random
      # prendo in considerazione solo mosse di attacco, che sono quelle che mi preoccupano di più
      if type_m==0:
        type_moves = [move for move in STANDARD_MOVE_ROSTER if move.type==pkm.type and move.power>0.0]
        pkm.moves[move_i] = random.choice(type_moves)
        type_m = 1
      else:
        # faccio in modo che sia diversa dalle mosse che ho già
        move = random.choice(STANDARD_MOVE_ROSTER)
        while(move in pkm.moves):
          move = random.choice(STANDARD_MOVE_ROSTER)
        pkm.moves[move_i] = move

def known_opp_moves(pkm: Pkm) -> int:
  known = 0
  for move_i in range(DEFAULT_N_ACTIONS-2):
    if pkm.moves[move_i].name is not None:
      known += 1
  return known

def stage_eval(team: PkmTeam) -> int:
  stage: int = 0
  for s in team.stage:
    stage += s
  return stage

def status_eval(pkm: Pkm) -> float:
  if pkm.status == (PkmStatus.CONFUSED or PkmStatus.PARALYZED or PkmStatus.SLEEP or PkmStatus.FROZEN):
    return -1
  elif pkm.status == (PkmStatus.BURNED or PkmStatus.POISONED):
    return -0.5
  else:
    return 0
  
def game_state_eval(g: GameState, depth: int):
  my_team = g.teams[0]
  opp_team  = g.teams[1]
  my_active: Pkm = my_team.active
  opp_active: Pkm = opp_team.active
  match_up: float = match_up_eval(my_active.type, opp_active.type,
      list(map(lambda m: m.type, my_active.moves)),
      list(map(lambda m: m.type, [move for move in opp_active.moves if move.name != None])))
  #print(f'MATCH UP: {match_up}')
  my_stage = stage_eval(my_team)
  opp_stage = stage_eval(opp_team)
  my_status = status_eval(my_active)
  opp_status = status_eval(opp_active)
  return (match_up 
          + my_active.hp/my_active.max_hp*3
          - opp_active.hp/opp_active.max_hp*3
          + 0.2*my_stage
          - 0.2*opp_stage
          + my_status
          - opp_status
          - 0.3*math.ceil(depth/2)
          + (my_team.party[0].hp/my_team.party[0].max_hp+my_team.party[1].hp/my_team.party[1].max_hp)*2)

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

class MixedPolicy(BattlePolicy):

  def __init__(self, max_depth: int = 6, seed: int = 69):
    self.max_depth = max_depth
    random.seed(seed)

  def get_action(self, g: GameState) -> int:
    root: Node = Node()
    root.gameState = g
    
    #print('---------------------------------')
    # print('OPPONENT MOVES')
    # for i in range(DEFAULT_N_ACTIONS-2):
    #   print(f'{str(g.teams[1].active.moves[i])}')
    # print('OPPONENT PKM')
    # print(g.teams[1])
    # print('---------------------------------')

    # se conosco meno di 2 mosse non utilizzo minimax ma una più semplice
    if known_opp_moves(g.teams[1].active)<2:
      return self.simple_search(root.gameState)
    # altrimenti faccio minimax
    else:
      # stimo delle mosse dell'avversario che non conosco
      estimate_move(root.gameState.teams[1].active)
      return self._alphaBeta_search(root)

  def simple_search(self, g: GameState) -> int:

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

  def _alphaBeta_search(
      self,
      root: Node,
      alpha: float = -np.inf,
      beta: float = np.inf
  ) -> int:
    #print("ALPHA BETA SEARCH")
    value, move = self._max_value(root, alpha, beta)
    #print('---------------------------------')
    #print(f'AlphaBetaPolicy chose action: {root.gameState.teams[0].active.moves[move]}, with value: {value}')
    #print('---------------------------------')
    return move

  def _max_value(
      self,
      node: Node,
      alpha: float,
      beta: float
  ) -> tuple[float, Union[int, None]]:
    state: GameState = deepcopy(node.gameState)
    # print('---------------------------------')
    # print(f'CURRENT NODE: {str(node)}')
    # print('---------------------------------')
    # print(f'MY HP: {state.teams[1].active.hp}')
    # print(f'OPPONENT HP: {state.teams[1].active.hp}')
    if state.teams[1].active.hp == 0 or state.teams[0].active.hp == 0 or node.depth >= self.max_depth:
      return game_state_eval(state, node.depth), None
    value = -np.inf
    for i in range(DEFAULT_N_ACTIONS):
      next_node: Node = Node()
      next_node.parent = node
      next_node.depth = node.depth + 1
      next_node.action = i
      next_node.gameState = state
      next_node.value, _ = self._min_value(next_node, alpha, beta)
      # print('---------------------------------')
      # print(f'NEXT NODE: {str(next_node)}')
      # print('---------------------------------')
      if next_node.value > value:
        value, move = next_node.value, next_node.action
        alpha = max(value, alpha)
      if value >= beta:
        return value, move
    return value, move
        
  def _min_value(
      self,
      node: Node,
      alpha: float,
      beta: float
  ) -> tuple[float, Union[int, None]]:
    state: GameState = deepcopy(node.gameState)
    value = np.inf
    for i in range(DEFAULT_N_ACTIONS):
      next_state, _, _, _, _ = state.step([node.action, i])
      next_node: Node = Node()
      next_node.parent = node
      next_node.depth = node.depth + 1
      next_node.action = i
      next_node.gameState = next_state[0]
      next_node.value, _ = self._max_value(next_node, alpha, beta)
      if next_node.value < value:
        value, move = next_node.value, next_node.action
        beta = min(value, beta)
      if value <= alpha:
        return value, move
    return value, move

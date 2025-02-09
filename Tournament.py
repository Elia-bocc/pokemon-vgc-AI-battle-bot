import threading
from tqdm import tqdm

from bots.AlphaBetaPolicy import AlphaBetaPolicy
from bots.MixedPolicy import MixedPolicy
from bots.GreedyPolicy import GreedyPolicy
from bots.fCompetitor import fCompetitor
from bots.Thunder_BattlePolicies import ThunderPlayer
from bots.hayo5 import hayo5_BattlePolicy

from vgc.competition.BattleMatch import BattleMatch
from vgc.competition.Competitor import CompetitorManager
from vgc.util.generator.PkmRosterGenerators import RandomPkmRosterGenerator
from vgc.util.generator.PkmTeamGenerators import RandomTeamFromRoster

from vgc.behaviour.BattlePolicies import TerminalPlayer, Minimax, PrunedBFS
import pandas as pd
import multiprocessing
from itertools import combinations

def main():
    c1 = fCompetitor('Player1') #Greedy
    c2 = fCompetitor('Player2') #AlphaBeta (4.0)
    c3 = fCompetitor('Player3') #Mixed (2.0)
    c4 = fCompetitor('Player4') #Mixed (4.0)
    c5 = fCompetitor('Player5') #PrunedBFS
    c6 = fCompetitor('Player6') #MiniMax
    c7 = fCompetitor('Player7') #Thunder
    c8 = fCompetitor('Player8') #Hayo5
    c9 = fCompetitor('Player9') #Mixed (6.0)
    c10 = fCompetitor('Player10') #AlphaBeta (2.0)

    #assing policies to competitors
    c1._battle_policy = GreedyPolicy()
    c2._battle_policy = AlphaBetaPolicy(4)
    c3._battle_policy = MixedPolicy(2)
    c4._battle_policy = MixedPolicy(4)
    c5._battle_policy = PrunedBFS()
    c6._battle_policy = Minimax()
    c7._battle_policy = ThunderPlayer()
    c8._battle_policy = hayo5_BattlePolicy()
    c9._battle_policy = MixedPolicy(6)
    c10._battle_policy = AlphaBetaPolicy(2)

    cm1 = CompetitorManager(c1)
    cm2 = CompetitorManager(c2)
    cm3 = CompetitorManager(c3)
    cm4 = CompetitorManager(c4)
    cm5 = CompetitorManager(c5)
    cm6 = CompetitorManager(c6)
    cm7 = CompetitorManager(c7)
    cm8 = CompetitorManager(c8)
    cm9 = CompetitorManager(c9)
    cm10 = CompetitorManager(c10)
    
    roster = RandomPkmRosterGenerator().gen_roster()
    tg = RandomTeamFromRoster(roster)

    cm1.team = tg.get_team()
    cm2.team = tg.get_team()
    cm3.team = tg.get_team()
    cm4.team = tg.get_team()
    cm5.team = tg.get_team()
    cm6.team = tg.get_team()
    cm7.team = tg.get_team()
    cm8.team = tg.get_team()
    cm9.team = tg.get_team()
    cm10.team = tg.get_team()

    T = Tournament([[cm1, "Greedy"], [cm2,"AlphaBeta4"], [cm5,"PrunedBFS"], 
                     [cm7, "Thuder"],[cm8,"Hayo5"], [cm9,"Mixed6"]])
    
    results = T.start_tournament()
    print(f"Results: {results}")
    df = pd.DataFrame(list(results.items()), columns=['Policy', 'Score'])
    standings = df.sort_values(["Score"], ascending=False).reset_index(drop=True)
    standings.index = standings.index + 1
    print(standings)
    standings.to_csv('tournament7.csv', index_label="Rank")

class Tournament():

    def __init__(self, competitors):
        policies = [i[1] for i in competitors]
        count = [0] * len(competitors)
        self.results = dict(zip(policies, count))  
        print(self.results)
        self.c = competitors
            
    def battle_match(self, team1, team2, debug=False):
        match = BattleMatch(team1, team2, debug=debug)
        match.run()
        return match.winner()
    
    def battle_worker(self, pair):
        i, j = pair
        wins_i = 0
        wins_j = 0
        for _ in range(2):  
            for _ in range(5):  
                winner = self.battle_match(i[0], j[0])
                if winner == 0:
                    wins_i += 1
                elif winner == 1:
                    wins_j += 1
            #switch teams
            i[0].team, j[0].team = j[0].team, i[0].team
        print("Match finished")
        return([i[1],wins_i], [j[1],wins_j])

    
    def start_tournament(self):
        print("Starting tournament...")
        team_combinations = list(combinations(self.c, 2))
        with multiprocessing.Pool() as pool:
            partial_results = pool.map(self.battle_worker, team_combinations)
            print(partial_results)
        print("Tournament finished.")

        for res in partial_results:
            self.results[res[0][0]] += res[0][1]
            self.results[res[1][0]] += res[1][1]
        return self.results

if __name__=='__main__':
    main()
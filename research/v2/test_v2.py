"""Scientific correctness checks; no report seeds are used."""
import itertools
import json
import unittest
from pathlib import Path
import numpy as np
from confirmation_planner import (PlannerInputs,optimize_plan,expand_plan,predictable_bounds,Z95)
from opv_bernstein import CubicOPV,bernstein,lipschitz_certificate
from opv_confirmation import (Case,Action,World,HistoryModel,features,make_cases,
                              campaign,BOUNDED_METHODS,inference,THRESHOLD)

HERE=Path(__file__).resolve().parent


class V2ScientificChecks(unittest.TestCase):
    def test_bernstein_basis_and_certificate(self):
        rng=np.random.default_rng(100001)
        x=rng.dirichlet(np.ones(4),100)
        y=rng.dirichlet(np.ones(4),100)
        np.testing.assert_allclose(bernstein(x).sum(axis=1),1,atol=1e-14)
        for system in ["pbq_qf","ptb7_th"]:
            f=CubicOPV.from_saved(system)
            self.assertGreaterEqual(f.lipschitz_l1,lipschitz_certificate(f.degradation_coefs))
            self.assertTrue(np.all(abs(f(x)-f(y))<=f.lipschitz_l1*np.abs(x-y).sum(axis=1)+1e-12))

    def test_four_component_mass_balance_and_fresh_state(self):
        case=Case("pbq_qf","test","test",.4,.2,.05,.5,.3,.04)
        world=World(CubicOPV.from_saved("pbq_qf"),case,100001)
        x=np.array([.1,.2,.3,.4]);before=world.h.copy()
        _,private=world.assay(Action(x,washes=1),noise=0)
        expected=.92*x+.08*before
        np.testing.assert_allclose(private["actual"],expected)
        np.testing.assert_allclose(world.h,.95*before+.05*expected)
        before=world.h.copy()
        _,private=world.assay(Action(x,fresh=True),noise=0)
        np.testing.assert_array_equal(world.h,before)
        np.testing.assert_array_equal(private["actual"],x)
        self.assertAlmostEqual(sum(private["actual"]),1)

    def test_count_optimizer_matches_all_sequences(self):
        for lam in [1.,.4,.04]:
            info=PlannerInputs(1.8,.5,.3,lam,budget=4,fresh_cost=2)
            best=optimize_plan(info)["half_width"]
            options=[{"washes":0,"fresh":False},{"washes":1,"fresh":False},
                     {"washes":3,"fresh":False},{"washes":0,"fresh":True}]
            direct=[]
            for n in range(2,5):
                for seq in itertools.product(options,repeat=n):
                    c=sum(info.fresh_cost if a["fresh"] else 1+a["washes"]*info.wash_cost for a in seq)
                    if c<=info.budget:
                        b=predictable_bounds(seq,info)
                        direct.append(np.mean([r["bias_bound"] for r in b])+Z95*info.sigma/np.sqrt(n))
            self.assertAlmostEqual(best,min(direct),places=13)

    def test_equal_cost_fresh_dominates(self):
        plan=optimize_plan(PlannerInputs(1.8,.5,.3,.4,budget=8,fresh_cost=1))
        self.assertEqual(plan["n_fresh"],8)
        self.assertEqual(plan["mean_bias_bound"],0)
        self.assertAlmostEqual(plan["half_width"],Z95*.03/np.sqrt(8))

    def test_interval_and_prespecified_tail_formula(self):
        ys=[.8,.81,.82,.83,.92,.94]
        bs=[.4,.2,.1,.05,.02,.01]
        stats=inference(ys,bs,"bounded_tail4",None,None)
        self.assertAlmostEqual(stats["mean"],.93)
        self.assertAlmostEqual(stats["mean_bias_bound"],.015)
        self.assertAlmostEqual(stats["half_width"],.015+Z95*.03/np.sqrt(2))

    def test_policy_state_contains_no_response_oracle(self):
        model=HistoryModel(.5,.3)
        self.assertEqual(set(vars(model)),{"rhos","etas","mean","cov","logw","h"})
        model.update(Action(np.array([.2,.3,.4,.1])),.85)
        self.assertAlmostEqual(model.weights().sum(),1)
        self.assertTrue(np.all(model.rhos<=.5))
        self.assertTrue(np.all(model.etas<=.3))

    def test_main_and_sensitivity_case_counts(self):
        protocol=json.loads((HERE/"protocol_draft.json").read_text())
        cases=make_cases(protocol)
        self.assertEqual(len(cases),32)
        self.assertEqual(sum(c.n_campaigns for c in cases),4800)
        self.assertEqual(sum(c.condition=="main" for c in cases),16)
        self.assertTrue(all(c.rho<=c.rho_upper and c.eta<=c.eta_upper and c.memory_lambda>=c.lambda_lower for c in cases))

    def test_full_development_campaign_bound_and_pairing(self):
        case=Case("pbq_qf","test","test",.4,.2,.05,.5,.3,.04)
        rows,example=campaign(100007,case,record=True)
        results={r["method"]:r for r in rows}
        self.assertEqual(len(rows),13)
        by_method=example["confirmation"]
        # Same routine action sequence and noise gives identical observations.
        for method in ["tail_repeat4","bounded_repeat","bounded_tail4","history_repeat"]:
            np.testing.assert_array_equal([r["y"] for r in by_method["candidate_repeat"]],
                                          [r["y"] for r in by_method[method]])
        truth=rows[0]["true_clean_response"]
        for method in BOUNDED_METHODS:
            row=results[method]
            self.assertLessEqual(row["cost"],32+1e-9)
            self.assertEqual(sum(row[k] for k in ["accepted","rejected","unresolved"]),1)
            for t in by_method[method]:
                actual_bias=abs(t["private"]["latent_response"]-truth)
                self.assertLessEqual(actual_bias,t["predictable_bias_bound"]+1e-12)
        self.assertAlmostEqual(results["bounded_planner"]["ci_halfwidth"],results["bounded_planner"]["planned_halfwidth"],places=13)


if __name__=="__main__":unittest.main()

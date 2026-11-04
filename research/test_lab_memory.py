"""Deterministic scientific checks of mixing, inference and budget accounting."""
import unittest
import numpy as np
from lab_memory import (Action, BayesianLinear, HistoryModel, Surface, World,
                        Regime, REGIMES, METHODS, SIGMA, features, action_cost,
                        available_active_actions, discovery, run_confirmation)


class ScientificChecks(unittest.TestCase):
    def test_fixed_final_mass_and_fresh_isolation(self):
        world = World(Surface(3), Regime("check", .4, .2), 1)
        nominal = np.array([.2, .5, .3])
        _, private = world.assay(Action(nominal), noise=0)
        np.testing.assert_allclose(private["actual"], .6*nominal+.4*np.array([1,0,0]))
        self.assertAlmostEqual(sum(private["actual"]), 1.)
        self.assertTrue(np.all(np.array(private["actual"]) >= 0))
        before = world.h.copy()
        _, private = world.assay(Action(nominal, fresh=True), noise=0)
        np.testing.assert_array_equal(world.h, before)
        np.testing.assert_array_equal(private["actual"], nominal)

    def test_no_carryover_and_wash_effect(self):
        x = np.array([.2, .5, .3])
        for washes in (0, 1, 3):
            world = World(Surface(3), Regime("check", 0, .8), 1)
            _, private = world.assay(Action(x, washes=washes), noise=0)
            np.testing.assert_array_equal(private["actual"], x)
        world = World(Surface(3), Regime("check", .4, .2), 1)
        _, private = world.assay(Action(x, washes=3), noise=0)
        self.assertAlmostEqual(private["retained_fraction"], .4*.2**3)

    def test_repetition_flushes_geometrically(self):
        rho = .4
        world = World(Surface(3), Regime("check", rho, .2), 1)
        h0 = world.h.copy()
        x = np.array([.2,.5,.3])
        for n in range(1,8):
            _, private = world.assay(Action(x), noise=0)
            np.testing.assert_allclose(private["actual"], x+rho**n*(h0-x), atol=1e-14)

    def test_quadratic_feature_representation(self):
        rng = np.random.default_rng(35)
        points = rng.dirichlet([1,1,1], 100)
        for seed in range(10):
            surface = Surface(seed)
            np.testing.assert_allclose(features(points)@surface.coefs,surface(points),atol=1e-14)
        np.testing.assert_allclose(features(points).sum(axis=1),1)

    def test_sequential_blr_matches_batch_reference(self):
        rng = np.random.default_rng(38)
        phi = features(rng.dirichlet([1,1,1], 15))
        y = rng.normal(.8,.1,15)
        model = BayesianLinear()
        for p,value in zip(phi,y):
            model.update(p,value)
        precision = 4*np.eye(6)+phi.T@phi/SIGMA**2
        cov = np.linalg.inv(precision)
        mean = cov@(4*np.full(6,.6)+phi.T@y/SIGMA**2)
        np.testing.assert_allclose(model.mean,mean,atol=1e-12)
        np.testing.assert_allclose(model.cov,cov,atol=1e-12)

    def test_one_step_gain_is_nonnegative_and_bounded(self):
        common = discovery(4,REGIMES[2])
        model = common["model"]
        candidate = common["candidate"]
        var = model.target(candidate)["variance"]
        for action in available_active_actions(candidate):
            cost = action_cost(action,REGIMES[2])
            gain = model.utility(action,candidate,cost)*cost
            self.assertGreaterEqual(gain,-1e-12)
            self.assertLessEqual(gain,var+1e-12)

    def test_private_truth_not_part_of_policy_state(self):
        model = HistoryModel()
        # The complete observation interface is commanded action + observed y.
        a = Action(np.array([.2,.3,.5]))
        model.update(a,.8)
        self.assertEqual(set(vars(model)),{"rhos","etas","mean","cov","logw","h"})
        self.assertAlmostEqual(model.weights().sum(),1)

    def test_budget_caps_and_resource_accounting(self):
        regime = Regime("check",.4,.2,wash_cost=.1,fresh_cost=8)
        common = discovery(8,regime)
        for method in METHODS:
            row,trace=run_confirmation(common,method,8,regime,budget=16,record=True)
            self.assertLessEqual(row["cost"],16+1e-9)
            self.assertAlmostEqual(row["cost"],sum(t["cost"] for t in trace))
            self.assertEqual(row["assays"],len(trace))
            self.assertEqual(row["washes"],sum(t["action"]["washes"] for t in trace))
            self.assertEqual(row["target_assays"],sum(np.allclose(t["action"]["nominal"],common["candidate"]) for t in trace))
            self.assertEqual(sum(row[k] for k in ["accepted","rejected","unresolved"]),1)

    def test_conditioning_at_candidate_counts_as_target(self):
        regime = REGIMES[2]
        common = discovery(8,regime)
        common["candidate"] = np.array([1.,0.,0.])
        common["predecessor"] = common["candidate"].copy()
        row,_=run_confirmation(common,"sequence_repeat",8,regime,budget=2)
        self.assertEqual(row["target_assays"],2)


if __name__ == "__main__":
    unittest.main()

"""APA 7 reference strings for the JICT submission of When the Lab Remembers.

The journal's template states "All manuscripts submitted to JICT must follow the APA 7th
edition referencing style." The master's catalog numbers its sources 1 to 13 and is
publisher-neutral by its own convention, so each entry here was written against the catalog
string for that number, and in-text citations map the master's [n] to author-date. The
catalog number is the key so the manuscript blocks need no rewriting to cite.
Bibliographic titles keep their own punctuation and are PROTECTED.
"""
APA = {
 1: ('Engel, K. M., Willi, P. O., Grass, R. N., & Stark, W. J. (2025). An automated platform '
     'for ‘on-demand’ high-speed catalyst synthesis by flame spray pyrolysis. Digital '
     'Discovery, 4(12), 3478–3491. https://doi.org/10.1039/D5DD00042D', 'Engel et al., 2025'),
 2: ('Quinn, H., Robben, G. A., Zheng, Z., Gardner, A. L., Werner, J. G., & Brown, K. A. (2024). '
     'PANDA: A self-driving lab for studying electrodeposited polymer films. Materials Horizons, '
     '11(21), 5331–5340. https://doi.org/10.1039/D4MH00797B', 'Quinn et al., 2024'),
 3: ('Roussel, R., & Hanuka, A. (2021). Towards hysteresis aware Bayesian regression and '
     'optimization. In Proceedings of the 12th International Particle Accelerator Conference '
     '(IPAC2021), TUPAB289. https://doi.org/10.18429/JACoW-IPAC2021-TUPAB289',
     'Roussel & Hanuka, 2021'),
 4: ('Bojinov, I., Simchi-Levi, D., & Zhao, J. (2023). Design and analysis of switchback '
     'experiments. Management Science, 69(7), 3759–3777. '
     'https://doi.org/10.1287/mnsc.2022.4583', 'Bojinov et al., 2023'),
 5: ('Delley, Y., Coller, J., Cutts, Z., Daryin, A., Bellaiche, M., Kim, J. W., Donosa, O., '
     'Seshadri, S. B., Clary, T., Klemm, S., Hassidim, A., Matias, Y., Rao, P., Sirkovic, P., & '
     'Pawlosky, A. (2026). Semantic representation for agentic self-play in automated '
     'laboratories [Preprint, submitted 23 October 2026]. arXiv. '
     'https://doi.org/10.48550/arXiv.2610.32755', 'Delley et al., 2026'),
 6: ('Tahara-Arai, Y., Kato, A., Ochiai, K., Azumi, K., Takahashi, K., Kanda, G. N., & Ozaki, H. '
     '(2026). GEMS: A deterministic finite automaton framework for adaptive laboratory '
     'automation. Digital Discovery, 5, 1411–1424. https://doi.org/10.1039/D5DD00409H',
     'Tahara-Arai et al., 2026'),
 7: ('Harris, S. B., Vasudevan, R., & Liu, Y. (2025). Active oversight and quality control in '
     'standard Bayesian optimization for autonomous experiments. npj Computational Materials, '
     '11, 23. https://doi.org/10.1038/s41524-024-01485-2', 'Harris et al., 2025'),
 8: ('Wei, A.-T., Liu, S., Lenhert, S., & Wang, H. (2024). Improving Bayesian optimization via '
     'hierarchical variation modeling for combinatorial experiments given limited runs guided '
     'by process knowledge. Knowledge-Based Systems, 305, 112596. '
     'https://doi.org/10.1016/j.knosys.2024.112596', 'Wei et al., 2024'),
 9: ('Häse, F., Aldeghi, M., Hickman, R. J., Roch, L. M., Christensen, M., Liles, E., Hein, '
     'J. E., & Aspuru-Guzik, A. (2021). Olympus: A benchmarking framework for noisy '
     'optimization and experiment planning. Machine Learning: Science and Technology, 2(3), '
     '035021. https://doi.org/10.1088/2632-2153/abedc8', 'Häse et al., 2021'),
 10: ('Howard, S. R., Ramdas, A., McAuliffe, J., & Sekhon, J. (2021). Time-uniform, '
      'nonparametric, nonasymptotic confidence sequences. The Annals of Statistics, 49(2), '
      '1055–1080. https://doi.org/10.1214/20-AOS1991', 'Howard et al., 2021'),
 11: ('Langner, S., Häse, F., Perea, J. D., Stubhan, T., Hauch, J., Roch, L. M., Heumueller, '
      'T., Aspuru-Guzik, A., & Brabec, C. J. (2020). Beyond ternary OPV: High-throughput '
      'experimentation and self-driving laboratories optimize multicomponent systems. Advanced '
      'Materials, 32(14), 1907801. https://doi.org/10.1002/adma.201907801',
      'Langner et al., 2020'),
 12: ('McShane, E. J. (1934). Extension of range of functions. Bulletin of the American '
      'Mathematical Society, 40(12), 837–842. '
      'https://doi.org/10.1090/S0002-9904-1934-05978-0', 'McShane, 1934'),
 13: ('Armstrong, T. B., & Kolesár, M. (2020). Simple and honest confidence intervals in '
      'nonparametric regression. Quantitative Economics, 11(1), 1–39. '
      'https://doi.org/10.3982/QE1199', 'Armstrong & Kolesár, 2020'),
}


def sort_key(n: int) -> str:
    return APA[n][0].split(',')[0].lower()

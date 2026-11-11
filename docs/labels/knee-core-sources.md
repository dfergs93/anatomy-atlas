# Core knee label text: sources (2026-11-10)

Sources behind the 24 drafted `labels/*.json` files for the spec §7.1 core knee set, for the owner's review. All files are `reviewed: false` until the owner flips them.

How they were made: four writers drafted one anatomical group each from the literature (PubMed / Europe PMC abstracts, PMC full texts, TA2 term data; Radiopaedia links confirmed from search results because Radiopaedia refuses automated fetches). Two independent fact-checkers then traced every number to its primary paper and found 10 WRONG and 13 UNSUPPORTED statements; all were corrected (second commit on this branch, listed under "Fact-check corrections" below). The writers' notes that follow are as written before the fact-check: **where they disagree with the corrections list, the correction wins.**

## Fact-check corrections

| File | Severity | What changed |
|---|---|---|
| medial_meniscus_anterior_horn | UNSUPPORTED | Transverse ligament pseudotear: 22% lateral (Watanabe 1989) vs 4 of 68 in Kang 2021; the untraced 38% and "original description" removed (Herman 1988 described it medially) |
| medial_meniscus_anterior_horn | UNSUPPORTED | Anomalous anterior horn insertion: "about 1–15%, mostly from small case series" (no primary prevalence study) |
| medial_meniscus_posterior_root | WRONG | Partial-height cleft is a partial root tear, not striation; complete tear = full-height cleft or missing root (Furumatsu 2021; SSR 2026) |
| medial_meniscus_posterior_root | UNSUPPORTED | Root–PCL distance: ≈8 mm in cadavers (Johannsen 2012) but ≈3 mm on 7 T MRI (Marcus 2026) |
| lateral_meniscus_body | WRONG | Absent bow tie: prompts a search for the fragment, not a diagnosis (Watt 2000 sensitivity 71%, PPV 76%; also small/degenerate menisci, post-meniscectomy) |
| lateral_meniscus_body | WRONG | Discoid: ≥15 mm mid-coronal (SSR 2026); "more than half the plateau width" is a commonly used adult criterion, not coverage |
| lateral_meniscus_body | UNSUPPORTED | Plateau coverage 60–70% (58% on 3D MRI, Bloecker 2011) |
| lateral_meniscus_posterior_horn | WRONG | Magic angle: T2 fading does not exclude a tear; surfacing signal on ≥2 short-TE slices or distortion is a tear |
| lateral_meniscus_posterior_horn | WRONG | Wrisberg extent ≥4 images "raises the possibility" of a tear (Park 2007: 5 tears; normal mean 3.0 images) |
| lateral_meniscus_posterior_root | UNSUPPORTED | Fascicle behind the PCL only in the single triple-root knee (1 of 57; Marcus 2026) |
| ligament_of_wrisberg | UNSUPPORTED | Slightly thicker than Humphry in cadavers (2.0 vs 1.5 mm), equal in one MRI series (1.8 vs 1.9 mm) |
| ligament_of_wrisberg | (link) | Radiopaedia link changed to the dedicated posterior-meniscofemoral-ligament-of-wrisberg article |
| pcl | WRONG | Double PCL sign vs ligament of Humphry: thin (≈1.5–2 mm), traceable to the lateral meniscus; confirm a fragment with absent bow tie and truncated body |
| femur | WRONG | Carrillon 2000 sensitivity/specificity are for patellar instability, not dysplasia |
| femur | UNSUPPORTED | Cortical irregularity sites: medial gastrocnemius 93–95%, lateral gastrocnemius 4–5%, adductor magnus 0–4% (Stern 2020) |
| fibula | UNSUPPORTED | Proximal tibiofibular joint–knee communication 10–64% reported; 25% was 3 of 12 cadavers (Dirim 2007) |
| mcl_superficial | WRONG | Watanabe's normal stripe was on non-fat-sat 0.35 T; on fat-sat only a thin sharp fluid line between the layers is normal, ill-defined signal around the sMCL is edema |
| mcl_superficial | UNSUPPORTED | Pellegrini–Stieda ossification can lie in the adductor magnus tendon (3 of 9, Mendes 2006) |
| lcl | UNSUPPORTED | 65/20/15 failure split is from multiligament injuries (Kahan 2020); 55% bone bruise is acute grade III PLC injuries (Geeslin 2010) |
| popliteus_tendon | UNSUPPORTED | Origin relative to LCL: 17–19 mm distal and anterior (Western/Indian series) vs ≈9 mm, mostly directly below (Korean series) |
| popliteus_tendon | UNSUPPORTED | Thickness: mean 3.8 mm, ≈2.8 mm in women in one series |
| popliteus_tendon | UNSUPPORTED | Indistinct popliteomeniscal fascicles alone are not a tear (unclear in 26–40% of controls, Suganuma 2012) |
| arcuate_ligament | WRONG | Arcuate sign: PCL injury (7 tears, 6 tibial avulsions) in 13 of 13 (Huang 2003); the 89% cruciate figure belongs to larger LCL/biceps fragments (Juhng 2002) |
| arcuate_ligament | WRONG | Surgical denominator: 6 of the 10 knees explored, not 6 of 13 |
| patella | (link) | Related: medial patellar retinaculum instead of vastus lateralis (the dislocation pitfall points medially) |

Checkers' optional notes not acted on: `pcl` quotes Gupte 2002's single-series MFL prevalence while the ligament files lead with pooled values; the Shin RSNA 2014 abstract (lcl, biceps_femoris_tendon) was also published as Shin Y et al., J Korean Soc Magn Reson Med 2014.

Both checkers confirmed: all TA2 terms correct, all Radiopaedia URLs exist (from search results), all related ids are checklist ids, and every 2024–2026 source cited exists in PubMed.


## Report: cruciates and bones (acl, pcl, femur, tibia, fibula, patella)



Method: PubMed abstracts via NCBI E-utilities; open PMC full texts via WebFetch; Radiopaedia blocks fetches (402/406), URLs confirmed from search results (title or /articles/<slug>/revisions page); TA2 terms checked in the FIPAT 2019 TA2 PDF by term number.

### Writer's uncertainties
- Femur ta2_name "Os femoris": TA2 uses it for the bone and gives "Femur" (TA2 160) to the thigh; TA98 preferred "Femur".
- ACL–Blumensaat cutoffs vary (>0°, ~11°, >15°); wrote "normal about 0° or negative" with cutoff range.
- Normal PCL thickness only as inverse of tear threshold (≥7 mm, Rodriguez 2008); control mean paywalled.
- PCL size (32–38 mm; 1.2–2× ACL cross-section) from review snippets only.
- ACL mucoid degeneration "about 1–14%": 14% upper bound from a review, untraced.
- Bipartite patella: Saupe type I ~1% (Radiopaedia) vs ~5% elsewhere (wrote 1–5%); prevalence 1–2% (CMAJ 2–6%).
- Wiberg percentages from a cadaver study and one clinical series, not Wiberg 1941.
- Caton–Deschamps upper limit 1.2 (Caton, Dejour) or 1.3 (Radiopaedia); both given.
- PTFJ–knee communication: 10% (Resnick 1978), 25% (one cadaver abstract); Radiopaedia's untraced 60% dropped.
- Ogden 1974 (20° cutoff; oblique ~70% of dislocations) from secondary reviews only.
- Tibial physeal scar sloping anteriorly into tuberosity: standard anatomy, no imaging citation.
- Red marrow rule "isointense to or brighter than muscle on T1" (Arslan 2015).

### acl
- TA2: Ligamentum cruciatum anterius (TA2 1890) = TA98. Radiopaedia: https://radiopaedia.org/articles/anterior-cruciate-ligament (revisions page; alias /articles/acl).
- Length 32 mm, width 7–12 mm in extension, AM/PL bundles: Duthon 2006, KSSTA 14:204, PMID 16235056.
- Bundles named by tibial insertion; striation from fat/connective tissue; seen on ≥2 contiguous sagittal images; PCL not striated; partial-volume pseudomass, check coronal/axial: Nissman 2008, Applied Radiology 37(12):25.
- Gentili 1994, Radiology 193:835, PMID 7972834 (sens/spec): ACL–tibial plateau angle <45° 90/97; ACL–Blumensaat >15° 89/100; bone contusions 54/100; PCL angle <107° 52/94; anterior tibial translation >7 mm 41/91; lateral femoral sulcus >1.5 mm 19/100.
- Mellado 2004, KSSTA 12:217, PMID 14530852: ACL angle 45° 100/100; Blumensaat 0° 90/98; PCL angle 115° 70/82.
- Celikyay 2020, J Belg Soc Radiol 104:36 (PMC7333554): Blumensaat sign convention (meet proximally negative, distally positive); mucoid 2–14% (review); tear vs mucoid: ATT >5 mm 70% vs 14%, contusions 65% vs 2%.
- Chan 1994, AJR 162:355, PMID 8310927: ATT >5 mm 86/99 at mid lateral femoral condyle.
- Bergin 2004, AJR 182:1283, PMID 15100133 (4221 MRIs): mucoid 1.04%; ACL ganglia 1.3%; both 35%; cysts femoral footprint 65%, tibial 27%; no instability 48/52.
- Hovis 2012, Skeletal Radiol 41:1435, PMID 22366737: mucoid 9.2% (28/304), OAI symptomatic OA cohort.
- Bui-Mansfield 1997, AJR 168:123, PMID 8976934: ACL ganglia 0.57% (10/1767); intra-articular ganglia 1.3%.
- Vahey 1991, Radiology 181:251, PMID 1887042: 30% of chronic complete tears look like an intact band.
- Kosarek 1999, AJR 172:481, PMID 9930807: infrapatellar plica mistaken for intact ACL.

### pcl
- TA2: Ligamentum cruciatum posterius (TA2 1891) = TA98. Radiopaedia: https://radiopaedia.org/articles/posterior-cruciate-ligament (revisions page; alias /articles/pcl).
- Rodriguez 2008, AJR 191:1031, PMID 18806138: AP diameter ≥7 mm on sagittal T2 highly suggestive of tear; torn PCLs keep continuity; signal higher on PD than T2; control mean unknown.
- Size 32–38 mm; cross-section 40–60 mm², 1.2–2× ACL: review snippets (PMC6105479; 2021 KSSTA review).
- PCL angle: Gentili 1994, Mellado 2004.
- Magic angle in proximal PCL: Radiopaedia "Magic angle effect" (snippet).
- Buckling with hyperextension with intact ACL: Nissman 2008.
- MFLs cadaver: ≥1 in 93%; Humphry 74%, Wrisberg 69%: Gupte 2002, JBJS Br 84:846 (abstract snippet).
- MFLs MRI: ≥1 in 93/100; Wrisberg 90 vs Humphry 17: Cho 1999, Skeletal Radiol 28:189, PMID 10384988.
- Humphry mimics (flipped fragment, loose body, PCL thickening): Nissman 2008.
- Arcuate sign: PCL injury 13/13: Huang 2003, AJR 180:381, PMID 12540438.
- Chronic tears heal lax/elongated: Radiopaedia PCL tear (snippet).

### femur
- TA2: Os femoris (TA2 1360); TA98 "Femur" with "Os femoris" synonym; TA2 "Femur" (160) = thigh (endnote 179). Radiopaedia: https://radiopaedia.org/articles/femur.
- Red marrow: >half of women, <1/6 of men; peak women 30–60; obesity, smoking: Wilson 1996, Acad Radiol 3:550, PMID 8796716.
- Red marrow hyperplasia 3% volunteers, 15% patients, 43% marathon runners; distal femur only, epiphysis and proximal tibia spared: Shellock 1992, AJR 158:335, PMID 1729795.
- Red marrow iso- to hyperintense to muscle on T1, metaphysis only: Arslan 2015, Pol J Radiol 80:300 (PMC4467604).
- FOPE: 15 zones 2–27 mm, ages 11.75–15.7; 8 femoral, 6 tibial, 1 fibular: Zbojniewicz & Laor 2011, AJR 197:998, PMID 21940591.
- Cortical irregularity: 27% control adolescents, 58% youth alpine skiers; 92.8–95.2% at medial gastrocnemius attachment: Stern 2020, Radiology 296:411, PMID 32544036. 9.1% adolescent MRIs: Gaukroger 2025, J Orthop 68:72, PMID 40007523. Bilateral ~1/3 (Radiopaedia snippet); 7/7 (Yamazaki 1995, PMID 7709251).
- Condylar ossification variants 22.2% of children, 99.6% posterior, peak 2–12 boys, 2–10 girls: Jans 2011, Radiology 258:880, PMID 21177387. Variant vs OCD: Gebarski 2005, Pediatr Radiol 35:880, PMID 15940391.
- Trochlear depth ≤3 mm at 3 cm above joint line 100/96; facet ratio <2:5: Pfirrmann 2000, Radiology 216:858, PMID 10966723.
- Lateral trochlear inclination <11° 93/87: Carrillon 2000, Radiology 216:582, PMID 10924589 (level from Radiopaedia, PMC5084520 snippets).
- Lateral femoral notch >1.5 mm: Gentili 1994.

### tibia
- TA2: Tibia (TA2 1397) = TA98. Radiopaedia: https://radiopaedia.org/articles/tibia.
- TT–TG ≥20 mm pathologic on CT; 56% of unstable knees; 3–6.5% of controls: Dejour 1994, KSSTA 2:19, PMID 7584171.
- TT–TG MRI 14.7 vs CT 16.9 mm; gap 3.8 mm in ≥20 mm subgroup: Camp 2013, AJSM 41:1835, PMID 23857884.
- Proximal tibia spared by red marrow hyperplasia: Shellock 1992.
- Cruciate footprint cysts ~1% of knee MRIs, mostly incidental: McLaren 1992, Skeletal Radiol 21:365, PMID 1523431. Tibial footprint 27% of ACL ganglion/mucoid: Bergin 2004.
- FOPE 6/15 tibial: Zbojniewicz 2011.
- Posterior lip medial tibial plateau contusion 12% of trauma MRIs; ACL tear 100%; meniscocapsular/peripheral MM tear 96%: Kaplan 1999, Radiology 211:747, PMID 10352601.

### fibula
- TA2: Fibula (TA2 1427) = TA98. Radiopaedia: https://radiopaedia.org/articles/fibula. normal_values {}.
- Ogden 1974: horizontal <20°, oblique >20°; oblique ~70% of 43 subluxations/dislocations (secondary: PMC4598538, MDedge, J Orthop Trauma).
- PTFJ–knee communication 10% adults (Resnick 1978, AJR, snippet); 25% cadaver (Dirim 2007 RSNA abstract, snippet).
- Peroneal intraneural ganglion via articular branch (unified articular theory): de Ruiter, Spinner, J Neurosurg 2025;143:1642, PMID 40614272.
- Arcuate sign: fragment 8–10 × 2–5 mm horizontal; PCL injury 13/13; 2 edema only: Huang 2003.

### patella
- TA2: Patella (TA2 1390) = TA98. Radiopaedia: https://radiopaedia.org/articles/patella.
- Insall–Salvati 0.8–1.2 radiographs: Insall & Salvati 1971, Radiology 101:101, PMID 5111961.
- IS on MRI mean 1.1 ± 0.1, alta >1.3: Miller 1996, AJR 167:339, PMID 8686598. Alta >1.50, baja <0.74: Shabshin 2004, Skeletal Radiol 33:445, PMID 15221214.
- Caton–Deschamps 0.6–1.2 (Radiopaedia case, Thieme review) vs 0.6–1.3 (Radiopaedia article); Dejour 1994 ≥1.2.
- PTI mean 31.7% (CI 12.5–50): Biedert & Albrecht 2006, KSSTA 14:707, PMID 16496126. Alta <12.5%, infera >50%: Biedert 2026, Knee 58:104263, PMID 41219080.
- Bipartite 0.7% of knee MRIs; fragment edema 66%; only finding 49%; 75% male: Kavanagh 2007, Skeletal Radiol 36:209, PMID 17151849.
- Bipartite 1–2%; Saupe I 5%, II 20%, III 75%: Zabierek 2016 (PMC5046971). Radiopaedia snippet: bilateral 43%, M:F ~9:1, type I ~1%. CMAJ 2008: 2–6%.
- Dorsal defect: 0.3–1% of radiographs; bilateral 25–33%; 2nd–3rd decades; ~1 cm; intact cartilage, no fragment: Gerrie 2016 (PMC5019194); Safran 1994 (PMID 7962501).
- Wiberg: I 7.7%, II 64.9%, III 27.4% (168 cadaver patellae); I 16.1%, II 80%, III 12.9% healthy knees (Servien) — snippets.
- Lateral patellar dislocation: inferomedial osteochondral injury 70%, impaction 44%, LFC contusion 80%, loose bodies 15%: Elias 2002, Radiology 225:736, PMID 12461254. Not suspected clinically 73%: Kirsch 1993, AJR 161:109, PMID 8517287.

### Additional
- Normal Blumensaat mean ~2.5° (Korean study, snippet) supports wording; no number stated.
- ACL–tibial plateau angle method-dependent (Celikyay ≤36°); kept 45° (Gentili, Mellado).
- ACL ganglion 0.6–1.3% (Bui-Mansfield, Bergin); a review's 0.12–0.44% unverified, left out.
- Biedert PTI protocol specifies relaxed quadriceps; file says "knee extended".

## Report: medial group (medial_meniscus_anterior_horn, _body, _posterior_horn, _posterior_root, mcl_superficial, mcl_deep)



### TA2 (checked in ta2viewer.openanatomy.org data)
- Four meniscus files: "Meniscus medialis" (TA2 1888); TA2 has no horn/body/root terms.
- mcl_superficial: "Pars superficialis ligamenti collateralis tibialis" (TA2 1897, under Ligamentum collaterale tibiale 1896).
- mcl_deep: "Pars profunda ligamenti collateralis tibialis" (TA2 1898). TA2 also lists Ligamentum meniscotibiale mediale (1902); no medial meniscofemoral term.

### Radiopaedia (fetches blocked 402/406; confirmed via search results)
- https://radiopaedia.org/articles/knee-menisci (three thirds) — revisions page "Knee menisci"; no separate medial meniscus article found.
- https://radiopaedia.org/articles/meniscal-root-tear (posterior root) — chosen because a reader clicking the root likely wants root-tear help.
- https://radiopaedia.org/articles/medial-collateral-ligament (both MCL files) — "Medial collateral ligament of the knee".
- Also exist: ghost-meniscus, absent-bow-tie-sign-knee, anomalous-insertion-of-the-medial-meniscus, medial-collateral-ligament-injury-grading.

### medial_meniscus_anterior_horn
- Medial anterior root single dark bundle; lateral anterior root mixed signal: Wang P, Medicine 2018;97:e0624 (qualitative).
- Transverse ligament seen on MRI 54–67%: 54.4% (105/193) Rodríguez C, Rev Argent Anat Clin 2022;14:15–21; 67.3% (68/101) Kang CW, Arthroscopy 2021;37:588–597.
- Transverse ligament in cadavers 34–94%: 34.3% Brown AA, MLTJ 2013;3:210; 71.4% Rodríguez 2022; 94% (47/50) Nelson & LaPrade, AJSM 2000;28:74–76.
- Transverse ligament pseudotear of lateral anterior horn 22–38% of exams: Watanabe AT, AJR 1989;153:341–344 (full text; cites earlier work).
- Only 1 medial (3 lateral) pseudotear among 68 knees with visible ligament: Kang 2021.
- Berlet–Fowler insertion types I 59%, II 24%, III 15%, IV 3% (34 of 48 cadaver knees): Berlet & Fowler, AJSM 1998;26:540–543.
- Transverse ligament the main anterior horn anchor in 24%: Nelson & LaPrade 2000.
- Anomalous insertion into ACL/notch ≈1–2% (up to 15%): SECOND-HAND (Eur J Radiol Open 2020 and J Clin Diagn Res 2025 case reports quote 1.2–2.3%; World J Methodol 2023;13:359 review quotes 1.2–15%).
- Pseudoradial tear on coronal 78.6% (381/485) on 1–5 sections, no true radial tear in 96 arthroscoped: You WY, J Korean Soc Magn Reson Med 2014;18:219–224 (single study).
- Flipped meniscus: anterior horn ≥8 mm tall; 9/10 lateral: Haramati N, Skeletal Radiol 1993;22:273–277.
- Posterior horn always larger than anterior horn: Radiology Assistant "Meniscus basics"; Radiopaedia lecture snippet.
- Oblique meniscomeniscal ligament 1–4%: SECOND-HAND (Chan & Goldblatt, Orthopedics 2012;35:e1815, citing Sanders, Radiology 1999).

### medial_meniscus_body
- Medial meniscus covers ~50% of medial plateau: Bloecker K, BMC Musculoskelet Disord 2011;12:248 (3D DESS).
- Bow-tie: two sagittal images normal; absent bow tie sens 97% (32/33), spec 100%; displaced fragment 94%, double PCL 30%, truncated coronal 64%: Helms CA, AJR 1998;170:57–61.
- Two bow ties at 4 mm: Radsource Web Clinic (radsource.us/?p=2782); "2–3 at 3 mm with 1 mm gap": snippets only. Body width (9–12 mm) left out (sources disagree).
- Absent bow tie in 27.5% normal / 35% degenerated; body <9 mm in 56.4% women, 27.1% men: Lee YU, J Korean Radiol Soc 2000;42:181–186.
- Root tear in 42% (30/71) with >3 mm extrusion vs 3% (1/34) ≤3 mm: Costa CR, AJR 2004;183:17–23.
- Physiological extrusion mean 1.24 mm men, 1.83 mm women: Bloecker 2011.
- Measure at apex of medial tibial spine; max slice overestimates: Jones LD, KSSTA 2018;26:1152–1157.
- Flounce: 0.2% (6/3,159), 5 medial: Yu JS, Radiology 1997;203:513–515; 5% (22/441), gone in full extension in all but one: Park JS, AJR 2006;187:364–370; 11% (31/283), 80.6% in torn medial menisci: Kim HJ, Skeletal Radiol 2020;49:1277–1284.
- Inferiorly displaced flaps: Lecas LK, AJR 2000;174:161–164; superiorly displaced: Bassett AJ, Arthrosc Tech 2019;8:e727.
- Discoid medial meniscus 0.06–0.3% (2023 AJSM review snippet; other reviews 0.12–0.3%); body ≥11 mm 99% specific, horns continuous on ≥3 5-mm sagittal slices 93% specific: Samoto N, Magn Reson Imaging 2006;24:1157–1165 (single series, 4 torn cases).

### medial_meniscus_posterior_horn
- Ramp lesions 9–17% (DePhillipo background) / 15–42% (Taneja AK, Insights Imaging 2021;12:134).
- DePhillipo NN, AJSM 2017;45:2233–2237: 16.6% of 301 ACLR; MRI reports caught 48%; posteromedial tibial bone bruise in 72% (36/50).
- Sens 53.9–84.6%, spec 92.3–98.7%: Arner JW, KSSTA 2017;25:3955–3960. Pooled sens 71%, spec 94%: Koo B, AJSM 2020;48:2051–2059.
- MRI signs; red-zone rim intermediate signal: Taneja 2021.
- Ramp-like fluid in 35/100 consecutive knees, only 20% with ACL insufficiency: Porrino J, Eur J Radiol Open 2025;14:100647.
- Posteromedial recess / gastrocnemius bursa mimicking ramp: Radiol Med 2021 review (snippet).
- Meniscal signal children 66% vs adults 29%; 80% age 10, 65% age 13, 35% age 15: Takeda Y, JBJS Br 1998;80:463–467.
- Two-slice-touch raises medial PPV 91% → 94%: De Smet & Tuite, AJR 2006;187:911–914.
- Incidental tears 19–56% age 50–90; 61% of those with tears no pain: Englund M, NEJM 2008;359:1108–1115.

### medial_meniscus_posterior_root
- Johannsen AM, AJSM 2012;40:2342–2347 (12 cadavers): 9.6 mm posterior, 0.7 mm lateral to medial tibial eminence apex (11.5 mm straight line); 3.5 mm lateral to medial articular cartilage edge; 8.2 mm from nearest PCL attachment edge.
- Root anterior to PCL: Radiopaedia intercondylar area (snippet). Root next to PCL on sagittal: Radiology Assistant.
- Normal root striped signal: Wang 2018.
- Root tear = within 9–10 mm of attachment: 9 mm LaPrade classification (Radiopaedia; Furumatsu 2021); 10 mm other reviews.
- MRI sens 86–90%, spec 94–95%; coronal T2 most useful: Lee SY, AJR 2008;191:81–85.
- Ghost sign in 1/23 partial root tears: Furumatsu T, KSRR 2021;33:38.
- Extrusion 42% vs 3%: Costa 2004.
- SIFK, 253 knees: medial root/posterior horn radial tears 71.1%, 91% of those ≥3 mm extrusion: Clark SC, KSSTA 2024;32:2755–2761. (Not used: Feng 2024 meta-analysis ~62% root tears in SONK.)
- Other ghost-meniscus causes: Radiopaedia ghost-meniscus (snippet).

### mcl_superficial
- LaPrade RF, JBJS Am 2007;89:2000–2010 (8 cadavers): length 94.8 mm; femoral attachment 3.2 mm proximal, 4.8 mm posterior to medial epicondyle; distal tibial attachment 61.2 mm below joint line.
- Tibial attachment center 62.4 mm below joint line: Liu F, J Orthop Surg Res 2010;5:69.
- Athwal KK, KSSTA 2020 (PMC7669814): femoral attachment centered 1–2 mm proximal to epicondyle, enveloping it; proximal tibial attachment soft tissue only; distal strip 42–71 mm below plateau.
- Medial layers: De Maeseneer M, RadioGraphics 2000;20:S83.
- Thin fluid/fat stripe up to ~4 mm beside normal MCL: Watanabe 1989 (full text).
- Grading: Radiopaedia MCL injury grading (snippet).
- MCL edema without trauma 27/30 medial OA knees vs 2/30 controls: Bergin D, Skeletal Radiol 2002;31:14–18.
- Stener-like lesion 20/51 distal tears; "wave sign": Boutin RD, Skeletal Radiol 2020;49:747–756.
- Bursae: pes anserine (Radiopaedia, Radsource snippets); semimembranosus–TCL bursa (Rothstein CP, AJR 1996;166:875; Hennigan SP, JBJS Am 1994;76:1322); MCL bursa (De Maeseneer M, AJR 2001;177:911–917).
- Pellegrini–Stieda: Radiopaedia (snippet).
- "Isolated" ACL tears: sMCL injured 62% (72.6% midsubstance, 22.6% femoral, 4.8% tibial): Willinger L, KSSTA 2022;30:167–175.

### mcl_deep
- Meniscofemoral part ~3× longer, meniscotibial ~1.7× wider; tibial attachment center 6.5 mm below joint line: Liu 2010.
- LaPrade RF, AJSM online 26 Oct 2026 (PMID 42929523): femoral attachment 12.4 mm distal, 5.1 mm posterior to epicondyle (~10.6 mm distal to sMCL femoral attachment); tibial 2.2 mm below joint line; blends posteriorly with POL. VERY NEW, not yet in print.
- Athwal 2020: femoral 6 mm distal, 5 mm posterior to epicondyle; tibial ~8 mm below plateau. Description gives these only roughly; normal_values empty because series disagree.
- MCL bursa with femoral and tibial compartments: De Maeseneer 2001.
- Willinger 2022: dMCL injured in 31% of "isolated" ACL tears (93.4% meniscofemoral, 6.4% meniscotibial); associated with ramp lesions and MFC bone edema. Willinger "grade II" sMCL = complete superficial disruption, so file says "the more severe superficial MCL injuries".
- MRI overcalls meniscocapsular separation: only 9% of medial MRI diagnoses confirmed; meniscal displacement up to 10 mm without tear: Rubin DA, Radiology 1996;201:829–836.

### Writer's uncertainties
1. No medial-meniscus-only Radiopaedia article; root links to root-tear article (could switch to knee-menisci).
2. All four meniscus files use "Meniscus medialis".
3. sMCL femoral attachment differs LaPrade 2007 vs Athwal 2020; both given.
4. Anomalous insertion and oblique meniscomeniscal prevalences second-hand.
5. Flounce 0.2–11%.
6. "Two bow ties at 4–5 mm" standard; "2–3 at 3 mm" snippets only.
7. Ramp figures vary widely; Porrino 2025 nonspecificity warning included.
8. 79% pseudoradial from a single study.
9. Posterior horn: no normal_values.

## Report: lateral meniscus and meniscofemoral ligaments (lateral_meniscus_anterior_horn, _body, _posterior_horn, _posterior_root, ligament_of_humphry, ligament_of_wrisberg)



Method: Europe PMC abstracts, PMC full texts; Radiopaedia URLs from search results only (fetches 402/406); TA2 from FIPAT TA2 Part 2 PDF entries 1883–1908.

### Sources (short names)
Gupte 2002 JBJS Br 84:846 (84 cadaver knees, PMID 12211675); Gupte 2003 Arthroscopy 19:161 (review of 16 cadaver studies, 1,022 knees, PMID 12579149); Pekala 2021 pMFL OJSM meta-analysis (PMC7903841); Pekala 2021 aMFL OJSM meta-analysis (PMC7903842); Cho 1999 Skeletal Radiol 28:189 (PMID 10384988); de Abreu 2007 Skeletal Radiol 36:729 (PMID 17483944); Vahey 1990 AJR 154:1237; Park/Jacobson 2007 Skeletal Radiol 36:399 (PMID 17225148); Marcus 2026 Eur Radiol 7 T 3D DESS 57 knees (PMC13035561); SSR 2026 Nguyen JC et al. meniscal nomenclature consensus, Skeletal Radiol (PMC13424353); Johannsen 2012 AJSM (PMID 22962297); LaPrade 2014 AJSM 42:2386 (PMID 25106782); Watson 2015 KSSTA (PMID 24850241); Brody 2006 Radiology 239:805 (PMID 16714462); Ciatti 2021 (PMC8286212); Visnes 2025 Norwegian registry (PMC12743849); Asai 2020 KSSTA (PMID 31254029); Yoshihara 2025 KSSTA (PMC12205407); De Smet 2009 AJR (PMID 19155414); De Smet & Graf 1994 AJR 162:883 (PMID 8141016); Shankman 1997 Radiology 204:181 (PMID 9205243); Peterfy 1994 AJR 163:149 (PMID 8010202); Herman & Beltran 1988 Radiology 167:775 (PMID 3363139); Haramati 1993 Skeletal Radiol (PMID 8316871); Helms 1998 AJR 170:57 (PMID 9423600); Watt 2000 Clin Radiol (PMID 10964734); Magee 2002 Skeletal Radiol (PMID 12483428); Kim 2020 J Exp Orthop discoid review (PMC7550551); Johnson & De Smet 1999 Skeletal Radiol (PMID 10550532); Suganuma 2012 Arthroscopy (PMID 22265047); Sanders 1999 Radiology (PMID 10540664); Wrisberg-variant: Singh 2006 AJR (PMID 16861542), Moser 2007 (PMID 17106270), Yue 2011 (PMID 21340450).

### lateral_meniscus_anterior_horn
- Root lateral to and partly beneath ACL footprint: Radiopaedia knee menisci snippet; LaPrade 2014 ("deeply beneath the ACL in all specimens").
- Horns about equal height laterally: Radiopaedia lecture snippet (teaching statement, not a study).
- Speckled signal 7/11 volunteers; all 22 arthroscoped patients (selected for it on 2 consecutive sagittal PD) normal: Shankman 1997 (Radsource "up to 60%" not used).
- ACL covers 63.2% of root footprint: LaPrade 2014. 10-mm reamer injured root 4/6 cadaver knees: Watson 2015.
- Flipped meniscus ≥8 mm, 9/10 lateral: Haramati 1993.
- Inferior lateral genicular artery mimics lateral anterior horn tear: Herman 1988.
- Transverse ligament pseudotear: no number given, "either meniscus" (Watanabe 1989 22% lateral not opened).
- Radiopaedia: https://radiopaedia.org/articles/knee-menisci (alternative confirmed: /articles/speckled-anterior-horn-of-lateral-meniscus).

### lateral_meniscus_body
- Covers ~70% of lateral plateau; average width 11 mm: Kim 2020. No LCL attachment: Radiopaedia snippet.
- Discoid 0.4–17% overall; 3–5% Western, 10–15% Asian; bilateral 15–25%, 97% contralateral in Ahn series of young Asian men: Kim 2020.
- Discoid criteria: ≥15 mm mid-coronal; published cutoffs 13–17 mm; >half plateau; "3 bow ties on 5 mm slices" abandoned for 3–4 mm slices: SSR 2026 Recommendation 5.
- Wrisberg type (Watanabe III): no posterior meniscotibial/capsular attachment (Kim 2020, SSR 2026); posterior horn flipped forward mimicking bucket-handle (Yue 2011).
- Bow tie: 2 sagittal images normal; absent bow tie sens 97%, spec 100% (Helms 1998); sens 71% (Watt 2000). "About 4–5 mm slices" is the writer's inference.
- Radial tears most frequent in middle third; MRI sens 68%, 89% with fat-sat: Magee 2002.
- Radiopaedia: knee-menisci (alternative confirmed: /articles/discoid-meniscus).

### lateral_meniscus_posterior_horn
- Pseudotear 42/109 (39%), 35/42 oblique: Vahey 1990; 63% (87% oblique, 13% vertical): de Abreu 2007.
- Interface extent lateral to PCL (3 mm slices, 0.5 mm gap): intact mean 0.9 images Humphry, 3.0 Wrisberg; torn 4.7 and 4.5; ≥4 images possible tear; all 5 torn had ACL tears: Park 2007.
- With ACL tear, lateral tear sensitivity 0.94 → 0.69; tears more posterior/peripheral: De Smet 1994.
- Wrisberg rip: Radsource web clinic Oct 2003, Radiopaedia cases, SSR 2026.
- Magic angle: increased signal 31/42 (74%), 81% of those at 55–60°: Peterfy 1994.
- Popliteus tendon pseudotear: Herman 1988; no meniscotibial attachment at hiatus: SSR 2026.
- Popliteomeniscal fascicles both seen 64/66, better on T2: Johnson 1999; unclear/absent 40% superior, 26% inferior in controls, abnormal 100% with recurrent subluxation: Suganuma 2012.
- Radiopaedia: knee-menisci.

### lateral_meniscus_posterior_root
- Root center 4.2 mm medial, 1.5 mm posterior to lateral tibial eminence apex (5.3 mm direct): Johannsen 2012; 8.8 ± 1.3 mm from apex on 7 T: Marcus 2026.
- Marcus 2026: single roots into intercondylar area 77.8%, posterior slope of medial eminence 22.2%; some insertions posterior to PCL; two-peaked coronal root in 81.6% of double roots.
- SSR 2026: root order anterior→posterior: medial anterior, lateral anterior, lateral posterior, medial posterior; 1 (24–53%), 2 (42–76%), 3 (2–5%) fascicles normal; root zone 1 cm.
- Root tears with ACL tears: 9.8% (Brody 2006), 10% (Visnes 2025), 13.5% (Ciatti 2021); SSR 2026 12–15% of ACLR; more common with ACL tear (De Smet 2009).
- Signs: each alone 34–66% sens; any of 3 → 84.4% sens, 90.5% spec: Asai 2020. Ghost 14%; cleft/truncated triangle 79% sens, 95% spec: Yoshihara 2025.
- Extrusion 23% of lateral root tears; absent MFL more common with root tears and extrusion: Brody 2006. "Intact MFL can hold a root-torn meniscus in place" is writer's inference.
- Root–PCL distance left out (12.7 mm cadaver Johannsen vs 4.4 mm 7 T Marcus).
- Radiopaedia: https://radiopaedia.org/articles/meniscal-root-tear (seen only on images.radiopaedia.org mirror in results).

### ligament_of_humphry
- TA2: Ligamentum meniscofemorale anterius (1886) = TA98.
- Cadaver: 48.2% (Gupte 2003); 74% (Gupte 2002); 60.0% cadaver subgroup, 55.5% overall (Pekala 2021).
- MRI: 35.8% pooled, 29.7% at ≤1.5 T, 51.0% at 3 T (Pekala 2021).
- With Wrisberg 31.8% (Gupte 2003) to 50% (Gupte 2002); fewer with age (Gupte 2002).
- Thickness 1.5 mm, cross-section 8.4% of PCL (Pekala 2021); 1–3 mm on MRI, mean 1.9 (de Abreu 2007).
- Anteroinferior to PCL (Wrisberg posterosuperior): Radiopaedia snippet.
- Double PCL mimic: Radiopaedia double PCL article; J Orthop Case Rep 2017 (snippets).
- Interface 0.9 vs 4.7 images: Park 2007.
- Oblique meniscomeniscal ligament 1–4%: Am J Orthop 2017 snippet; Sanders 1999.
- "Bulge on the PCL": secondary summary of Watanabe 1989.
- Radiopaedia: https://radiopaedia.org/articles/meniscofemoral-ligament (shared with Wrisberg).

### ligament_of_wrisberg
- TA2: Ligamentum meniscofemorale posterius (1887) = TA98.
- Pekala 2021 pMFL: 70.4% pooled (74.1% cadaver, 66.5% MRI; 68.8% at 3 T, 60.1% at ≤1.5 T); thickness 2.3 mm (2.0 cadaver, 2.5 radiological); width 4.1 mm mid, 6.1 mm femoral; cross-section 14.1% of PCL.
- Marcus 2026 7 T: Wrisberg 50.9%, Humphry 35.1%, neither 12.3%; attachment along 8.3 ± 1.2 mm of posterior horn; fan-shaped femoral attachment.
- Cho 1999: Wrisberg 90, Humphry 17 of 100 MRIs; 47/90 Wrisberg appeared to attach to PCL.
- 94% on MRI, thickness 1–3.8 mm: de Abreu 2007.
- ≥1 MFL in 91.1% (Gupte 2003) to 93% (Gupte 2002).
- Oblique PCL fibers ("false pMFL") 19%: Gupte 2002.
- Pseudotear 39–63% (Vahey 1990, de Abreu 2007); interface 3.0 vs 4.5 images (Park 2007).
- Wrisberg variant: Kim 2020, Singh 2006, Moser 2007 (seen only when locked), Yue 2011; "absent fascicles"/"fluid cleft" from secondary snippets.
- Radiopaedia: meniscofemoral-ligament.

### Writer's choices
- All four meniscal files "Meniscus lateralis" (TA2 1885).
- Anterior root vs ACL: LaPrade 2014 anterolateral to ACL center vs SSR 2026 "posterolateral aspect of the ACL insertion"; wrote "just lateral to and partly beneath".
- Bintoudi 2012 (500 MRIs) not used: internally inconsistent numbers.
- Wrisberg-variant congenital status debated (SSR 2026, Kim 2020); not mentioned in body file.

## Report: LCL and posterolateral corner (lcl, popliteus_tendon, popliteus, popliteofibular_ligament, biceps_femoris_tendon, arcuate_ligament)



Method: abstracts via Europe PMC REST API (PMIDs given); Radiopaedia refuses automated fetches (402/406) so its URLs are confirmed from WebSearch results; TA2 terms checked against ta2viewer.openanatomy.org term data (IDs: lig. collaterale fibulare 1895, lig. popliteum arcuatum 1900, lig. popliteofibulare 1906, lig. fabellofibulare 1907, m. popliteus 2665, m. biceps femoris 2638, bursa subtendinea inferior m. bicipitis femoris 2744, recessus subpopliteus 2745, fabella 1395, cyamellus 1396).

Writer's flagged uncertainties:
- No TA2 tendon term for popliteus or biceps femoris tendon; used "Musculus popliteus" / "Musculus biceps femoris".
- "Arcuate sign" defined as small styloid avulsion (Lee 2003, Huang 2003); Juhng 2002's 89% cruciate figure is for radiographic fibular head avulsions incl. LCL/biceps fragments — worded as "radiographic fibular head avulsion" (biceps file) and "one series" (arcuate file).
- Popliteus origin vs LCL origin: 17–18.5 mm anterior+distal in Western series; ~9 mm mostly straight distal in a Korean series; wrote "about 1–2 cm, distal and usually anterior".
- Arcuate ligament presence in cadavers 24–100%; gave range plus Radiopaedia's ~65%.
- LCL between biceps arms 88% and true conjoined 0.4%: RSNA 2014 abstract only; labelled as abstract.
- Two-slip popliteus tendon ~35%: dissection only.
- LCL thickness 3–6 mm: rough size, not a threshold.

### lcl
- TA2: Ligamentum collaterale fibulare (= TA98). Radiopaedia: https://radiopaedia.org/articles/lateral-collateral-ligament-of-the-knee (search hit).
- Femoral attachment 1.4 mm proximal, 3.1 mm posterior to lateral epicondyle; fibular attachment 28.4 mm below styloid tip within biceps bursa: LaPrade AJSM 2003 (PMID 14623649); LaPrade 2021 J Arthrosc Surg Sports Med review "The Posterolateral Corner".
- Length ≈70 mm cadaver: LaPrade 2003 via 2021 review.
- Thickness 5.3 ± 1.0 mm MRI; signal alteration 33%, thickening 33% in stable knees (varus-linked): Choi Arthroscopy 2015 (PMID 25618492).
- Seen over 2–3 coronal slices: general teaching (MRI Online lecture).
- Normal proximal intermediate signal 79% of 77 knees, mean length 8.6 mm (mucin/fibrocartilage at enthesis): Falkowski J Ultrasound Med 2022 (PMID 34086999).
- FCL–biceps bursa present 50/50 knees, 8.4 × 18 mm: LaPrade & Hamilton AJSM 1997 (PMID 9240975).
- LCL between biceps arms 87.7%, true conjoined 0.4%, n = 494: Shin RSNA 2014 abstract.
- PLC multiligament LCL failure: fibular avulsion 65%, femoral 20%, midsubstance 15%; peroneal palsy 31%: Kahan AJSM 2020 (PMID 33074710).
- Anteromedial femoral condyle bone bruise in 55% PLC injuries: Geeslin & LaPrade 2010 via 2021 review (primary not read).
- Practically all LCL tears have other PLC injury: Recondo RadioGraphics 2000;20:S91.

### popliteus_tendon
- TA2: no tendon term; "Musculus popliteus". Radiopaedia: https://radiopaedia.org/articles/popliteus-tendon (search hit).
- Origin vs LCL origin: 18.5 mm always anterior (LaPrade 2003); 16.85 mm MRI anterior+distal (Saini J Clin Orthop Trauma 2021, PMID 33816110); 9.35 mm inferior, 0.89 mm posterior, anterior only 8% MRI / 21% cadaver (Kim Knee 2021, PMID 34492449).
- Length sulcus to MTJ 54.9 mm: LaPrade 2021 review.
- Thickness 3.8 ± 0.6 mm (Choi 2015); 3.61 mm men / 2.77 mm women coronal FS (Alasadi & Mohamed Surg Radiol Anat 2026, PMID 42587104).
- Subpopliteal recess extends 22.6 ± 11.4 mm below top of lateral tibial condyle (Tabira Clin Anat 2024, PMID 38419377).
- Recondo 2000: bursa fluid confused with tear; fluid behind tendon outside recess suggests capsular tear; <10% popliteus tears isolated; femoral avulsion = empty sulcus.
- Sheath mimicking LM posterior horn tear 55/200 (27.5%): Watanabe JBJS Am 1989 (PMID 2745483); Herman & Beltran Radiology 1988 (PMID 3363139).
- Double popliteus tendon sign: Lesniak Sports Health 2011 (PMID 23016032).
- Muscle involved in 23/24 popliteus injuries, isolated 8.3%: Brown Skeletal Radiol 1995 (PMID 8545647).
- Signal alteration 23%, thickening 8% in stable knees: Choi 2015.
- Two tendons in sulcus 34.7% of 134 cadaver limbs: Olewnik Sci Rep 2021 (PMID 34262097).
- Cyamella 0.57–1.8% literature, 1.4% CT: Berthaume & Bull Clin Anat 2021 (PMID 33905585).

### popliteus
- TA2: Musculus popliteus. Radiopaedia: https://radiopaedia.org/articles/popliteus-muscle (search hits incl. /articles/44427 "Popliteus muscle").
- Popliteal artery divides at lower border of popliteus: França J Vasc Bras 2024 (PMID 39764515).
- 24 popliteus injuries in 2,412 MRIs (≈1%); muscle in 23; isolated 8.3%; PCL torn 29.2%: Brown 1995.
- Recess fluid mimicking tear; retracted belly as mass: Recondo 2000.
- Aberrant anterior tibial artery anterior to popliteus: 2.03% of 787 MRIs, best seen at PCL tibial attachment 81% (Albishi OJSM 2025, PMID 40995416); 1.91% of 4,075 (Akcaalan OJSM 2025, PMID 41180580); 3.15% of 222 (Frey OJSM 2024, PMID 39711610); range 0.4–6% (Parekh 2026 scoping review, PMID 41783333; not quoted).

### popliteofibular_ligament
- TA2: Ligamentum popliteofibulare (TA98 status unverified). Radiopaedia: https://radiopaedia.org/articles/popliteofibular-ligament (search hit).
- Divisions: posterior 1.6 mm, anterior 2.8 mm distal to styloid tip: LaPrade 2003; 2021 review.
- Length 8.7 ± 2.5 mm, thickness 1.4 ± 0.4 mm coronal; seen 93.3% of 105 normal knees: Morales-Avalos KSSTA 2022 (PMID 34142172).
- Present at dissection: 88.3% of 137 (Olewnik Clin Anat 2022, PMID 35119143); 90.3% (Olewnik 2021); 10/10 (LaPrade 2003); 98% (Sudasna & Harnsiriwattanagit 1990, PMID 2163702).
- MRI visibility: 8% standard coronal vs 53% coronal oblique (Yu Radiology 1996, PMID 8539378); 38% routine (De Maeseneer Eur Radiol 2001, PMID 11702156); 70.8% coronal oblique FS T2 vs 91.0% 3D WE-DESS (Rajeswaran Skeletal Radiol 2007, PMID 17938917); 57% cadaver MRI (Munshi AJR 2003, PMID 12646462; not quoted).
- MRI accuracy for injury 68%: LaPrade AJSM 2000 (PMID 10750995).
- Abnormal in 19/22 surgically treated PLC injuries: Collins KSSTA 2015 (PMID 26239863).
- Small styloid fragment = PFL/arcuate; larger lateral fragment = LCL+biceps: Lee Skeletal Radiol 2003 (PMID 14520502).
- Morphology: single 72.3%, bifurcated 8.7%, double 7.3%: Olewnik 2022.

### biceps_femoris_tendon
- TA2: no tendon term; "Musculus biceps femoris". Radiopaedia: https://radiopaedia.org/articles/distal-biceps-femoris-tendon (search hit).
- Arms: long head anterior arm leaves 1 cm above fibular head, lateral to LCL; short head anterior arm inserts 1 cm posterior to Gerdy's tubercle: Terry & LaPrade AJSM 1996 (PMID 8638749); 2021 review.
- True conjoined 0.4%: RSNA 2014 abstract.
- Insertion variants on 403 MRIs: complete tibial ≈1%, predominantly tibial ≈10%: Malalagama Surg Radiol Anat 2020 (PMID 31781923).
- Snapping biceps: Radiopaedia snippet; Tagliero 2024 (PMID 40309049); Kress 2025 (PMID 41541309).
- Cruciate injury 16/18 with radiographic fibular head avulsion (fragments attached to LCL, biceps or both): Juhng AJR 2002 (PMID 11856678).
- Common peroneal nerve displaced in 16/18 avulsions: Bottomley JBJS Br 2005 (PMID 16129747).
- Peroneal palsy 9/16 distal biceps avulsions, every palsy with displaced nerve on MRI: Bloom Knee 2020 (PMID 33202291).
- Biceps complex injuries 72% of 82 acutely unstable knees; 89/92 to short head: Terry & LaPrade 1996.

### arcuate_ligament
- TA2: Ligamentum popliteum arcuatum (= TA98). Radiopaedia: https://radiopaedia.org/articles/arcuate-ligament (search hits incl. /articles/7989; snippet "~65% (range 47.9–71%)").
- Shape/course: Recondo 2000.
- Laminae (arcuate deep, fabellofibular superficial): Seebacher JBJS Am 1982 (PMID 7068696), abstract and secondary summaries only.
- Presence in cadavers: 24% (Sudasna 1990); 80% (Seebacher: arcuate alone 13% + both 67%); 100% sectional anatomy (Song Anat Rec 2018, PMID 30383338).
- MRI visibility: 10% standard coronal vs 46% coronal oblique (Yu 1996); 25% (De Maeseneer 2001); ≥1 limb in 71% cadaver specimens (Munshi 2003; not quoted).
- Reinforcement: arcuate alone 13%, fabellofibular alone 20%, both 67% (Seebacher 1982); fabellofibular parallel to LCL and inverse to arcuate (Radiopaedia snippet).
- Fabella: 25% overall, 32% dissection vs 19% radiographs (Asghar Cureus 2021, PMID 34084671); 36.8% (Berthaume 2019 via PMID 33088615); MRI 20.6% (PMID 36408308), 39.8% (PMID 35232412), 48.4% (PMID 33269861).
- Arcuate sign: fragment 8–10 × 2–5 mm horizontal from styloid; PCL injured 13/13; styloid marrow edema without visible fragment in 2; arcuate complex disruption invisible on MRI in 6 (Huang AJR 2003, PMID 12540438); 89% cruciate injury (Juhng 2002).
- Arcuate/fabellofibular not confidently characterized in surgical PLC injuries: Collins 2015.
- "Only fat behind the popliteus tendon": Recondo 2000.

### Writer's "verify" list
- 55% anteromedial bone bruise is second-hand (2021 review).
- Seebacher laminae from abstract/secondary only.
- TA98 status of popliteofibular ligament unverified.

# Knee MRI — structure checklist

Seed list for `data/knee-mri`. Edit freely — add, remove, rename.
**Type:** R = region (painted in label map) · P = point label.
**Labelled:** painted/placed in the case. **Content:** `labels/<id>.json` written and reviewed.

## Bones and landmarks

|id                       |Name                        |Type|Labelled|Content|
|-------------------------|----------------------------|----|--------|-------|
|femur                    |Femur                       |R   |[ ]     |[ ]    |
|tibia                    |Tibia                       |R   |[ ]     |[ ]    |
|fibula                   |Fibula                      |R   |[ ]     |[ ]    |
|patella                  |Patella                     |R   |[ ]     |[ ]    |
|medial_femoral_condyle   |Medial femoral condyle      |P   |[ ]     |[ ]    |
|lateral_femoral_condyle  |Lateral femoral condyle     |P   |[ ]     |[ ]    |
|trochlea                 |Femoral trochlea            |P   |[ ]     |[ ]    |
|intercondylar_notch      |Intercondylar notch         |P   |[ ]     |[ ]    |
|medial_tibial_plateau    |Medial tibial plateau       |P   |[ ]     |[ ]    |
|lateral_tibial_plateau   |Lateral tibial plateau      |P   |[ ]     |[ ]    |
|intercondylar_eminence   |Intercondylar eminence      |P   |[ ]     |[ ]    |
|tibial_tuberosity        |Tibial tuberosity           |P   |[ ]     |[ ]    |
|gerdys_tubercle          |Gerdy’s tubercle            |P   |[ ]     |[ ]    |
|fibular_head             |Fibular head                |P   |[ ]     |[ ]    |

## Cartilage

|id                       |Name                        |Type|Labelled|Content|
|-------------------------|----------------------------|----|--------|-------|
|femoral_cartilage        |Femoral cartilage           |R   |[ ]     |[ ]    |
|medial_tibial_cartilage  |Medial tibial cartilage     |R   |[ ]     |[ ]    |
|lateral_tibial_cartilage |Lateral tibial cartilage    |R   |[ ]     |[ ]    |
|patellar_cartilage       |Patellar cartilage          |R   |[ ]     |[ ]    |

## Menisci

|id                              |Name                              |Type|Labelled|Content|
|--------------------------------|----------------------------------|----|--------|-------|
|medial_meniscus_anterior_horn   |Medial meniscus — anterior horn   |R   |[ ]     |[ ]    |
|medial_meniscus_body            |Medial meniscus — body            |R   |[ ]     |[ ]    |
|medial_meniscus_posterior_horn  |Medial meniscus — posterior horn  |R   |[ ]     |[ ]    |
|lateral_meniscus_anterior_horn  |Lateral meniscus — anterior horn  |R   |[ ]     |[ ]    |
|lateral_meniscus_body           |Lateral meniscus — body           |R   |[ ]     |[ ]    |
|lateral_meniscus_posterior_horn |Lateral meniscus — posterior horn |R   |[ ]     |[ ]    |
|medial_meniscus_posterior_root  |Medial meniscus posterior root    |P   |[ ]     |[ ]    |
|lateral_meniscus_posterior_root |Lateral meniscus posterior root   |P   |[ ]     |[ ]    |

## Ligaments

|id                            |Name                                      |Type|Labelled|Content|
|------------------------------|------------------------------------------|----|--------|-------|
|acl                           |Anterior cruciate ligament                |R   |[ ]     |[ ]    |
|pcl                           |Posterior cruciate ligament               |R   |[ ]     |[ ]    |
|mcl_superficial               |MCL — superficial                         |R   |[ ]     |[ ]    |
|mcl_deep                      |MCL — deep (meniscofemoral/meniscotibial) |R   |[ ]     |[ ]    |
|posterior_oblique_ligament    |Posterior oblique ligament                |R   |[ ]     |[ ]    |
|lcl                           |Lateral (fibular) collateral ligament     |R   |[ ]     |[ ]    |
|popliteofibular_ligament      |Popliteofibular ligament                  |R   |[ ]     |[ ]    |
|arcuate_ligament              |Arcuate ligament                          |R   |[ ]     |[ ]    |
|anterolateral_ligament        |Anterolateral ligament                    |R   |[ ]     |[ ]    |
|oblique_popliteal_ligament    |Oblique popliteal ligament                |R   |[ ]     |[ ]    |
|ligament_of_humphry           |Anterior meniscofemoral lig. (Humphry)    |R   |[ ]     |[ ]    |
|ligament_of_wrisberg          |Posterior meniscofemoral lig. (Wrisberg)  |R   |[ ]     |[ ]    |
|transverse_meniscal_ligament  |Transverse (intermeniscal) ligament       |R   |[ ]     |[ ]    |
|mpfl                          |Medial patellofemoral ligament            |R   |[ ]     |[ ]    |
|medial_patellar_retinaculum   |Medial patellar retinaculum               |R   |[ ]     |[ ]    |
|lateral_patellar_retinaculum  |Lateral patellar retinaculum              |R   |[ ]     |[ ]    |

## Tendons

|id                        |Name                       |Type|Labelled|Content|
|--------------------------|---------------------------|----|--------|-------|
|quadriceps_tendon         |Quadriceps tendon          |R   |[ ]     |[ ]    |
|patellar_tendon           |Patellar tendon            |R   |[ ]     |[ ]    |
|popliteus_tendon          |Popliteus tendon           |R   |[ ]     |[ ]    |
|biceps_femoris_tendon     |Biceps femoris tendon      |R   |[ ]     |[ ]    |
|semimembranosus_tendon    |Semimembranosus tendon     |R   |[ ]     |[ ]    |
|semitendinosus_tendon     |Semitendinosus tendon      |R   |[ ]     |[ ]    |
|gracilis_tendon           |Gracilis tendon            |R   |[ ]     |[ ]    |
|sartorius_tendon          |Sartorius tendon           |R   |[ ]     |[ ]    |
|iliotibial_band           |Iliotibial band            |R   |[ ]     |[ ]    |
|pes_anserinus             |Pes anserinus              |P   |[ ]     |[ ]    |

## Muscles

|id                          |Name                          |Type|Labelled|Content|
|----------------------------|------------------------------|----|--------|-------|
|vastus_medialis             |Vastus medialis               |R   |[ ]     |[ ]    |
|vastus_lateralis            |Vastus lateralis              |R   |[ ]     |[ ]    |
|vastus_intermedius          |Vastus intermedius            |R   |[ ]     |[ ]    |
|rectus_femoris              |Rectus femoris                |R   |[ ]     |[ ]    |
|sartorius                   |Sartorius                     |R   |[ ]     |[ ]    |
|gracilis                    |Gracilis                      |R   |[ ]     |[ ]    |
|semimembranosus             |Semimembranosus               |R   |[ ]     |[ ]    |
|semitendinosus              |Semitendinosus                |R   |[ ]     |[ ]    |
|biceps_femoris              |Biceps femoris                |R   |[ ]     |[ ]    |
|gastrocnemius_medial_head   |Gastrocnemius — medial head   |R   |[ ]     |[ ]    |
|gastrocnemius_lateral_head  |Gastrocnemius — lateral head  |R   |[ ]     |[ ]    |
|plantaris                   |Plantaris                     |R   |[ ]     |[ ]    |
|popliteus                   |Popliteus                     |R   |[ ]     |[ ]    |
|soleus                      |Soleus                        |R   |[ ]     |[ ]    |

## Vessels and nerves

|id                                |Name                               |Type|Labelled|Content|
|----------------------------------|-----------------------------------|----|--------|-------|
|popliteal_artery                  |Popliteal artery                   |R   |[ ]     |[ ]    |
|popliteal_vein                    |Popliteal vein                     |R   |[ ]     |[ ]    |
|tibial_nerve                      |Tibial nerve                       |R   |[ ]     |[ ]    |
|common_peroneal_nerve             |Common peroneal (fibular) nerve    |R   |[ ]     |[ ]    |
|great_saphenous_vein              |Great saphenous vein               |P   |[ ]     |[ ]    |
|small_saphenous_vein              |Small saphenous vein               |P   |[ ]     |[ ]    |
|saphenous_nerve                   |Saphenous nerve                    |P   |[ ]     |[ ]    |
|superior_medial_genicular_artery  |Superior medial genicular artery   |P   |[ ]     |[ ]    |
|superior_lateral_genicular_artery |Superior lateral genicular artery  |P   |[ ]     |[ ]    |
|inferior_medial_genicular_artery  |Inferior medial genicular artery   |P   |[ ]     |[ ]    |
|inferior_lateral_genicular_artery |Inferior lateral genicular artery  |P   |[ ]     |[ ]    |
|middle_genicular_artery           |Middle genicular artery            |P   |[ ]     |[ ]    |

## Fat pads, recesses, bursae

|id                                 |Name                                   |Type|Labelled|Content|
|-----------------------------------|---------------------------------------|----|--------|-------|
|hoffa_fat_pad                      |Infrapatellar (Hoffa) fat pad          |R   |[ ]     |[ ]    |
|quadriceps_fat_pad                 |Suprapatellar (quadriceps) fat pad     |R   |[ ]     |[ ]    |
|prefemoral_fat_pad                 |Prefemoral fat pad                     |R   |[ ]     |[ ]    |
|suprapatellar_recess               |Suprapatellar recess                   |R   |[ ]     |[ ]    |
|semimembranosus_gastrocnemius_bursa|Semimembranosus–gastrocnemius bursa    |P   |[ ]     |[ ]    |
|prepatellar_bursa                  |Prepatellar bursa                      |P   |[ ]     |[ ]    |
|deep_infrapatellar_bursa           |Deep infrapatellar bursa               |P   |[ ]     |[ ]    |
|pes_anserine_bursa                 |Pes anserine bursa                     |P   |[ ]     |[ ]    |

#!/bin/bash
# Coordinator batch N1, 19 November 2026: the two noisy single-frequency BEM fits asked for by the baseline
# coordinator (user condition met). Waits for every measured fit, so these wall-limited fits run alone.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
until grep -q "BATCH DONE" $L/batch_02.state 2>/dev/null && grep -q "BATCH DONE" $L/batch_02b.state 2>/dev/null && grep -q "BATCH DONE" $L/batch_02c.state 2>/dev/null; do sleep 10; done
echo "$(date -u +%FT%TZ) start bem/default_n1d0_uc_sf0.5 circle__c4 kite__c4" >> $L/batch_n1.state
$P -m experiments.comparison run bem/default_n1d0_uc_sf0.5 --cases circle__c4 kite__c4 >> $L/batch_n1.log 2>&1
echo "$(date -u +%FT%TZ) end bem/default_n1d0_uc_sf0.5 exit=$?" >> $L/batch_n1.state
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_n1.state

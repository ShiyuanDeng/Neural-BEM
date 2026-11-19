#!/bin/bash
# Coordinator batch 02b, 19 November 2026: the two measured round-two fits, beside the two measured fits of batch 02.
# Starts when the TG-002 controls of batch 02 are done, so no wall-limited TG-002 fit shares the machine.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
until grep -q "TG CONTROLS DONE" $L/batch_02.state 2>/dev/null; do sleep 5; done
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
M=results/bem/baseline_data/measured_schedule/2026-11-19
mkdir -p $M/logs
echo "$(date -u +%FT%TZ) start measured circle_ladder and circle_then_ladder" >> $L/batch_02b.state
$P experiments/bem_on_baseline_data/csi_measured_warmups.py circle_ladder > $M/logs/circle_ladder_attempt_01.log 2>&1 &
A=$!
$P experiments/bem_on_baseline_data/csi_measured_warmups.py circle_then_ladder > $M/logs/circle_then_ladder_attempt_01.log 2>&1 &
B=$!
wait $A; echo "$(date -u +%FT%TZ) end measured circle_ladder exit=$?" >> $L/batch_02b.state
wait $B; echo "$(date -u +%FT%TZ) end measured circle_then_ladder exit=$?" >> $L/batch_02b.state
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_02b.state

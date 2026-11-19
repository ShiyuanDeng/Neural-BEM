#!/bin/bash
# Coordinator batch 02c, 19 November 2026: measured cylinder with frontier-capped bands, and its control.
# Starts at once, beside the measured fits still running; none of them has a binding wall limit.
cd /home/drdeng/Neural_SDF_BEM_AD_organised || exit 1
L=results/bem/stage_scheduling/2026-11-19/clean_tg002/logs
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
M=results/bem/baseline_data/measured_schedule/2026-11-19
mkdir -p $M/logs
echo "$(date -u +%FT%TZ) start measured frontier_capped and frontier_measured" >> $L/batch_02c.state
$P experiments/bem_on_baseline_data/csi_measured_frontier_caps.py frontier_capped > $M/logs/frontier_capped_attempt_01.log 2>&1 &
A=$!
$P experiments/bem_on_baseline_data/csi_measured_frontier_caps.py frontier_measured > $M/logs/frontier_measured_attempt_01.log 2>&1 &
B=$!
wait $A; echo "$(date -u +%FT%TZ) end measured frontier_capped exit=$?" >> $L/batch_02c.state
wait $B; echo "$(date -u +%FT%TZ) end measured frontier_measured exit=$?" >> $L/batch_02c.state
echo "$(date -u +%FT%TZ) BATCH DONE" >> $L/batch_02c.state

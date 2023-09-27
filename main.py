from datetime import date, datetime, timedelta

from infrastructure_builder import InfrastructureBuilder
from metric_data import MetricData
from workloads import run_workloads
from cloudwatch_monitor import CloudWatchMonitor

import time
import subprocess
import multiprocessing
import json

from matplotlib.dates import (DateFormatter)

def initialize_infra(infra_builder):
    print('Started initializing infrastructure.')

    security_group = infra_builder.create_security_group('custom-sec-group')

    user_data_cluster1 = open('flask_setup_cluster1.sh', 'r').read()
    user_data_cluster2 = open('flask_setup_cluster2.sh', 'r').read()
    m4_Instances = infra_builder.create_instances('m4.large', 5, 'ami-08c40ec9ead489470', 'vockey', user_data_cluster1, security_group.group_name)
    t2_Instances = infra_builder.create_instances('t2.large', 4, 'ami-08c40ec9ead489470', 'vockey', user_data_cluster2, security_group.group_name)

    elb = infra_builder.create_load_balancer('elb', security_group.id)

    cluster1_tg = infra_builder.create_target_group('cluster1')
    cluster2_tg = infra_builder.create_target_group('cluster2')

    infra_builder.register_targets(cluster1_tg, m4_Instances)
    infra_builder.register_targets(cluster2_tg, t2_Instances)

    listener = infra_builder.create_listener(cluster1_tg, elb)

    listener_rule_1 = infra_builder.create_path_forward_rule(cluster1_tg, listener, '/cluster1', 1)
    listener_rule_2 = infra_builder.create_path_forward_rule(cluster2_tg, listener, '/cluster2', 2)

    print('Finished initializing infrastructure.')

    return elb, security_group, m4_Instances, t2_Instances, listener, cluster1_tg, cluster2_tg

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def print_response(response):
    print('Saving query result in graphs/response.json.')
    with open("graphs/response.json", "w") as data_file:
        json.dump(response, data_file, indent=4, sort_keys=True, default=json_serial)

# PROGRAM EXECUTION

# 1. Generate infrastructure (EC2 instances, load balancers and target groups)
infra_builder = InfrastructureBuilder()
elb, sg, m4_instances, t2_instances, listener_cluster, cluster1_tg, cluster2_tg = initialize_infra(infra_builder=infra_builder)
time.sleep(90)

# 2. Run workloads
run_workloads(elb)

# 3. Build query to collect desired metrics from the last 30 minutes (estimated max workload time)
cloudwatch_monitor = CloudWatchMonitor()
query = cloudwatch_monitor.build_cloudwatch_query(m4_instances + t2_instances)

# 4. Query CloudWatch client using built query
response = cloudwatch_monitor.get_data(query)

# 5. Save output to response.json
print_response(response)

# 6. Parse MetricDataResults and store metrics
(tg_metrics_cluster1, tg_metrics_cluster2, elb_metrics, ecs_metrics) = cloudwatch_monitor.parse_data(response)

ecs_metrics = cloudwatch_monitor.group_ecs_metrics(ecs_metrics)

# 7. Generate graphs and save under /metrics folder
cloudwatch_monitor.generate_graphs(tg_metrics_cluster1, tg_metrics_cluster2, elb_metrics, ecs_metrics)

print('Done.')
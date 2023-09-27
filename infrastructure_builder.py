import boto3

class InfrastructureBuilder:

    def __init__(self):
        self.ec2_client = boto3.client('ec2')
        self.ec2_resource = boto3.resource('ec2')
        self.elb_client = boto3.client('elbv2')

    def create_security_group(self, name):
        response_vpcs = self.ec2_client.describe_vpcs()
        vpc_id = response_vpcs.get('Vpcs', [{}])[0].get('VpcId', '')

        response_security_group = self.ec2_client.create_security_group(
            GroupName=name,
            Description='Security group for our instances',
            VpcId=vpc_id)

        security_group_id = response_security_group['GroupId']
        
        self.ec2_client.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
        {'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        {'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])
        
        return self.ec2_resource.SecurityGroup(response_security_group['GroupId'])

    def create_instances(self, instance_type, count, image_id, key_name, user_data, security_group_name):
        return self.ec2_resource.create_instances(
            InstanceType=instance_type,
            MinCount=count,
            MaxCount=count,
            ImageId=image_id,
            KeyName=key_name,
            UserData=user_data,
            SecurityGroups=[security_group_name]
        )

    def create_load_balancer(self, name, security_group_id):
        subnets = []
        ec2_client_subnets = self.ec2_client.describe_subnets()
        for subnet in ec2_client_subnets['Subnets'] :
            subnets.append(subnet['SubnetId'])

        return self.elb_client.create_load_balancer(
            Name=name,
            SecurityGroups=[
                security_group_id
            ],
            IpAddressType='ipv4',
            Subnets= subnets
        )

    def create_target_group(self, name):
        response_vpcs = self.ec2_client.describe_vpcs()
        vpc_id = response_vpcs.get('Vpcs', [{}])[0].get('VpcId', '')
        
        return self.elb_client.create_target_group(
            Name=name,
            Protocol='HTTP',
            Port=80,
            VpcId=vpc_id
        )
    
    def get_targets(self, target_instances):
        targets = []
        for instance in target_instances:
            targets.append({
                "Id": instance.id
            })
        return targets
    
    def register_targets(self, target_group, instances):
        targets = self.get_targets(instances)

        for instance in instances:
            instance.wait_until_running()
        
        return self.elb_client.register_targets(
            TargetGroupArn=target_group['TargetGroups'][0]['TargetGroupArn'],
            Targets=targets
        )

    def create_listener(self, tg_cluster1, load_balancer):
        return self.elb_client.create_listener(
            DefaultActions=[
                {
                    'TargetGroupArn': tg_cluster1['TargetGroups'][0]['TargetGroupArn'],
                    'Type': 'forward',
                },
            ],
            LoadBalancerArn=load_balancer['LoadBalancers'][0]['LoadBalancerArn'],
            Port=80,
            Protocol='HTTP',
        )

    def create_path_forward_rule(self, tg_cluster, listener, path, priority):
        return self.elb_client.create_rule(
            ListenerArn = listener['Listeners'][0]['ListenerArn'],
            Conditions=[
                {
                    'Field': 'path-pattern',
                    'Values': [
                        path
                    ]
                }
            ],
            Priority=priority,
            Actions=[
                {
                    'Type': 'forward',
                    'ForwardConfig': {
                        'TargetGroups': [
                            {
                                'TargetGroupArn': tg_cluster['TargetGroups'][0]['TargetGroupArn'],
                                'Weight': 1
                            },
                        ],
                        'TargetGroupStickinessConfig': {
                            'Enabled': False,
                            'DurationSeconds': 1
                        }
                    }
                }
            ]
        )
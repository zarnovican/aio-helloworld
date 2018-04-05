# Deployment Tests

## Deploy - slowly starting service without healthcheck

`service1` has a 5s delay between process startup and serving http requests.

[test1.yaml](examples/test1.yaml)

To do the deploy, just change the value of env variable `VERSION`.

During deploy, there is a 5s period, when Swarm load-balancer is sending requests to a service
instance that is still starting. In the best case, 1 of N requests are failing on connection
refused. If there is no delay between deploy and you have only a small number of replicas (2),
then the whose service will go down.

Setting a delay between deploys will mitigate the impact, but there are still "1-of-N" requests
failing.
```
            update_config:
                delay: 10s
```

## Deploy - slowly starting service with healthcheck

In this case, Swarm will add the instance to load-balancer only after the healthcheck is green.
No matter what is the startup delay. There is no service disruption.

[test2.yaml](examples/test2.yaml)

## Deploy - failed service deploy without healthcheck

Here, you deploy an intentionally broken version of a service (`SELFDESTRUCT_DELAY: XXs`).
The problem here is that Swarm will not wait to see if the instance is ok.
When there is no healthcheck, he will move on and deploy second instance and so on.
The deployment is "paused" only after the first container failed. So, it may happen
that Swarm has already deployed 2-3 other instance with this broken version. After the deployment
is paused, you may end up with one to M broken and constantly restarted instances. The bad news is
that they are already in Swarm load-balancer, so M-of-N requests will be failing. In the worst case,
all instances will be updated with the broken version (M==N) leaving you with zero working
instances and deploy job in completed state (not paused).

[test3.yaml](examples/test3.yaml)
(to run the test, enable `SELFDESTRUCT_DELAY` env var)

Does this help ?
```
            update_config:
                monitor: 10s
```
`monitor` option does not prevent Swarm to move on to second instance after deploying the first.
It is not a time to monitor one instance deployment, rather it is monitoring time for the whole
deployment process.

## Deploy - failed service deploy with healthcheck

If the service has a healtcheck, the failed deploy is without outage. The problem is detected right
on the first instance and the whole process is paused.

[test4.yaml](examples/test4.yaml)

The problem is when the instance will crash _after_ its healthcheck becomes green. In this case,
deployment is also paused, but not on the first instance. There will be several instances constantly
restarted and re-added to the load-balancer. When they will crash again and again, they will cause
service disruptions for the time between crash and instance becoming "unhealthy". Unhealthy instance
will be removed from load-balancer and the whole process is repeated.

Would `monitor` help in this case ? No. It does not have any effect on detecting the failure early.
What it does is to keep deployment in "in progress" status even after all instances were redeployed.
This gives Swarm a chance to revert changes which fail relatively late. For example, if service will
run out of memory within 1min after deployment, but `monitor` is set to 2min, then the whole
deploy can be reverted automatically even _after_ all instances were updated.

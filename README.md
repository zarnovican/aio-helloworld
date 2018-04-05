# aio-helloworld

## Briefly

This is a Docker image to test deploys to Swarm. One of its http endpoints is `/info`
that will identify the instance within service.

```bash
$ curl http://vm5:30001/info
AIO Python test1_service1.1 (1.0.1) on 19d45eb40785: your IP 10.255.0.2
```
(it includes also service name, task slot, service version, container hostname and source IP)

It may be used to:
* test simple rolling deploy, measure service outage
* test inter-service connectivity within stack, multiple stacks, multiple networks
* test failing deploy and automated rollbacks
* test service logging to console/syslog

See [Deployment Tests](deployment.md) for examples of testing Swarm deployments on failure.

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

## HTTP Endpoints

* `/ping` - ping/pong check

    ```bash
    $ curl http://vm5:30001/ping
    pong
    ```

* `/info` - tell me who you are and on what version

    ```bash
    $ while :; do curl http://vm5:30001/info; sleep .1; done
    AIO Python stack_service1.4 (1.0.1) on 45802ca0fefb: your IP 10.255.0.2
    AIO Python stack_service1.3 (1.0.1) on 6cdd80eedf51: your IP 10.255.0.2
    AIO Python stack_service1.2 (1.0.1) on 8391d26c5553: your IP 10.255.0.2
    AIO Python stack_service1.1 (1.0.1) on 7458b912b073: your IP 10.255.0.2
    AIO Python stack_service1.4 (1.0.1) on 45802ca0fefb: your IP 10.255.0.2
    AIO Python stack_service1.3 (1.0.1) on 6cdd80eedf51: your IP 10.255.0.2
    ```

* `/slow/<time in ms>` - run slow request/response

    ```bash
    $ time curl http://vm5:30001/slow/100
    Slow response.

    real	0m0.124s
    user	0m0.008s
    sys	0m0.007s
    ```

* `/call/(service1|service2)/<url>` - make a remote call to another service (url configured by `SERVICE1_URL`)

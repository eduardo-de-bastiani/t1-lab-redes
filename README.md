# Cenários de Teste

1. Inicializa o servidor.

```bash
docker run -d --rm --name servidor --network lab-redes-net -p 127.0.0.1:65432:65432 lab-redes-app python -m server.server; docker logs -f servidor
```

2. Inicializa o cliente 1 em modo interativo.

```bash
docker run -it --rm --name cliente1 --network lab-redes-net --cap-add=NET_ADMIN -v "$(pwd)/client/logs:/app/client/logs" lab-redes-app /bin/bash

apt-get update && apt-get install -y iproute2

truncate -s 200M file_cliente1.bin
```

3. Inicializa o cliente 2 em modo interativo.

```bash
docker run -it --rm --name cliente2 --network lab-redes-net --cap-add=NET_ADMIN -v "$(pwd)/client/logs:/app/client/logs" lab-redes-app /bin/bash

apt-get update && apt-get install -y iproute2

truncate -s 200M file_cliente2.bin
```

## Cenário 1 - 1 Instância de Cliente sem Alteração de Interface de Rede

- No container do cliente1:

```bash
python -m client.client --host host.docker.internal --port 65432

list

put bigfile.bin

list

quit
```

## Cenário 2 - 2 a 4 Instâncias de Cliente sem Alteração de Interface de Rede

- No container do cliente1:

```bash
python -m client.client --host host.docker.internal --port 65432

list

put file_cliente1.bin

list

quit
```

- No container do cliente2:

```bash
python -m client.client --host host.docker.internal --port 65432

list

put file_cliente2.bin

list

quit
```

## Cenário 3 - 1 Instância de Cliente com Alteração de Interface de Rede

> ⚠️ **AVISO:** _Todos os comandos no Cliente 1._

```bash
tc qdisc add dev eth0 root handle 1: htb default 10
tc class add dev eth0 parent 1: classid 1:10 htb rate 10mbit ceil 10mbit
```

### Item i - Perda de Pacote

---

```bash
tc qdisc del dev eth0 parent 1:10
tc qdisc add dev eth0 parent 1:10 handle 10: netem loss 0.1%
```

```bash
truncate -s 200M file_cen3_i.bin
```

```bash
python -m client.client --host host.docker.internal --port 65432

list

put file_cen3_i.bin

list

quit
```

### Item ii - Latência Variável

---

```bash
tc qdisc del dev eth0 parent 1:10
tc qdisc add dev eth0 parent 1:10 handle 10: netem delay 50ms 10ms
```

```bash
truncate -s 200M file_cen3_ii.bin
```

```bash
python -m client.client --host host.docker.internal --port 65432

list

put file_cen3_ii.bin

list

quit
```

## Cenário 4 - 2 a 4 Instâncias de Cliente com Alteração de Interface de Rede

### Item i - Perda de Pacote

---

- No container do cliente1:

```bash
tc qdisc del dev eth0 parent 1:10
tc qdisc add dev eth0 parent 1:10 handle 10: netem loss 0.1%
```

```bash
truncate -s 200M file_cliente1_cen4_i.bin
```

- No container do cliente2:

```bash
tc qdisc del dev eth0 parent 1:10
tc qdisc add dev eth0 parent 1:10 handle 10: netem loss 0.1%
```

```bash
truncate -s 200M file_cliente2_cen4_i.bin
```

- No container do cliente1:

```bash
python -m client.client --host host.docker.internal --port 65432

list

put file_cliente1_cen4_i.bin

list

quit
```

- No container do cliente2:

```bash
python -m client.client --host host.docker.internal --port 65432

list

put file_cliente2_cen4_i.bin

list

quit
```

### Item ii - Latência Variável

---

- No container do cliente1:

```bash
tc qdisc del dev eth0 parent 1:10
tc qdisc add dev eth0 parent 1:10 handle 10: netem delay 50ms 10ms
```

```bash
truncate -s 200M file_cliente1_cen4_ii.bin
```

- No container do cliente2:

```bash
tc qdisc del dev eth0 parent 1:10
tc qdisc add dev eth0 parent 1:10 handle 10: netem delay 50ms 10ms
```

```bash
truncate -s 200M file_cliente2_cen4_ii.bin
```

- No container do cliente1:

```bash
python -m client.client --host host.docker.internal --port 65432

list

put file_cliente1_cen4_ii.bin

list

quit
```

- No container do cliente2:

```bash
python -m client.client --host host.docker.internal --port 65432

list

put file_cliente2_cen4_ii.bin

list

quit
```

### Cleanup da Interface de Rede

- No container de ambos os clientes (Cliente 1 e Cliente 2):

```bash
tc qdisc del dev eth0 root
```

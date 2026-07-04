# LotsoNet

<!-- ![lotsonet-logo](img/LotsoNet_logo.png | width=40) -->
<img src="img/LotsoNet_logo.png"  width="33%" />

## Resumo:

LotsoNet é um projeto de faculdade para a disciplina de Sistemas Distribuídos. Temos o intuito de construir uma rede P2P resiliente e descentralizada de Comando e Controle. 

## Como rodar:

### Rodando com docker:
(Exemplo): Rodando com 10 nós virtuais na rede:
```shell
docker-compose up -d --build --scale node=10 node
```
Agora você pode acessar uma das máquinas (exemplo: a máquina 1) utilizando:
```shell
docker attach lotsonet-node-1
```
E pode derrubá-las usando:
```shell
docker-compose down
```

### Rodando em diversos dispositivos:

TODO 

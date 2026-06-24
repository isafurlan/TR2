# Streaming Adaptativo com Controle de Banda
## Objetivo:  
Entender a distribuição de conteúdo multimídia 
na internet implementando um sistema 
de streaming adaptativo, com:
- servidor HTTP
- controle pragmático de banda e variação de atraso
- ABR
- failover automático

- Descrever o funcionamento do HTTP em modo chunked e sua relação com o TCP

- Implementar um servidor HTTP com controle de taxa de transferência programático

- Medir vazão e variação de atraso (jitter) de uma conexão TCP a partir da aplicação

- Implementar gestão de buffer com estimativa de continuous play e detecção de rebuffering

- Projetar e implementar pelo menos três algoritmos ABR distintos

- Implementar failover automático entre servidores com base em health check

- Correlacionar eventos da aplicação (rebuffering, failover, troca de qualidade) com comportamentos TCP visíveis no Wireshark

## Dependências:
pip install requests matplotlib

## Etapas:
### Criação de Virtual Enviroment (venv):
python3 -m venv tr2-trab  
source tr2-trab/bin/activate

python main.py --policy 1
python main.py --policy 2
python main.py --policy 3
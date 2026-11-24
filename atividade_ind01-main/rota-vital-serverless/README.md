# Rota Vital · Função serverless (guia de transporte)

Atividade individual 1 · Infraestrutura de Software · ADS · CESAR School · 2026.2
**Autor:** Mateus Henrique Diniz Silva
**Vídeo (até 3 min):** https://youtu.be/omYVfv3yMcA

Função serverless acionada **por evento** e **por HTTP** que recebe uma requisição do Rota Vital (`POST /guias`) e devolve a guia de transporte de bolsas de sangue.

## Caminho escolhido

**Caminho A: AWS SAM CLI local** (Docker + SAM CLI + Python 3.12). Tudo roda no meu computador (macOS), sem conta na AWS, sem cartão e sem publicar na nuvem.

## Estrutura

```
template.yaml          # API POST /guias, Timeout em Globals, 128 MB, python3.12
hello_world/app.py     # handler: lê o body, valida, gera a guia, contador global
hello_world/requirements.txt
events/pedido.json     # evento no formato API Gateway proxy (gerado com sam local generate-event)
evidencias/            # prints (.png) e saídas dos comandos (.txt)
README.md
.gitignore             # ignora .aws-sam/
```

## O que a função faz

Entrada (body JSON): `requisicaoId` (obrigatório), `hospital`, `bolsas` e `demorar` (opcional; se `true`, dorme 5 s para forçar o timeout).

| Caso | Resposta |
|---|---|
| body válido | `201` com `{"guia": "G-<requisicaoId>", "hospital": ..., "bolsas": [...], "invocacaoNesteAmbiente": N}` |
| sem `requisicaoId` | `400` com `{"erro": "requisicaoId obrigatório"}` |
| `demorar: true` e Timeout < 5 s | erro de tempo limite (HTTP 502 no `start-api`) |

`invocacaoNesteAmbiente` vem de uma variável global (`contador`) e serve para observar se o ambiente de execução foi reaproveitado.

## Como rodar

**Pré-requisitos:** Docker rodando, SAM CLI (`sam --version`), Python 3.12. No Windows, usar Git Bash ou WSL. Todos os comandos na raiz do repositório (onde está o `template.yaml`).

> O `template.yaml` entregue está com `Timeout: 10` (estado final, após o experimento do Passo 5). Para reproduzir o erro de timeout, troque para `3`, rode `sam build` e repita o curl do passo 5.

```bash
# 1. Build
sam build

# 2. Invocar com evento (rodar duas vezes e anotar o tempo)
sam local invoke -e events/pedido.json
sam local invoke -e events/pedido.json

# 3. Gatilho HTTP (sem reaproveitamento)
sam local start-api
# em outro terminal, três vezes:
curl -X POST http://127.0.0.1:3000/guias -H "Content-Type: application/json" \
  -d '{"requisicaoId":"R-002","hospital":"H-Caruaru"}'

# 4. Reaproveitamento do ambiente
# parar o servidor (Ctrl+C) e subir de novo:
sam local start-api --warm-containers LAZY
# repetir os três curls

# 5. Limite de tempo (com Timeout: 3 no template.yaml + sam build)
curl -X POST http://127.0.0.1:3000/guias -H "Content-Type: application/json" \
  -d '{"requisicaoId":"R-003","demorar":true}'
# depois: Timeout: 10, sam build, repetir o curl

# 6. Validação de entrada
curl -X POST http://127.0.0.1:3000/guias -H "Content-Type: application/json" \
  -d '{"hospital":"H-Teste"}'
```

O evento foi gerado com:

```bash
sam local generate-event apigateway aws-proxy --method POST --path guias \
  --body '{"requisicaoId":"R-001","hospital":"H-Recife","bolsas":["O-NEG-0142"]}' > events/pedido.json
```

## Evidências (pasta `evidencias/`)

| Item | Print | Saída em texto |
|---|---|---|
| Versão do SAM CLI | `01-sam-version.png` | — |
| `sam build` | `02-build.png` | — |
| `sam local invoke` | `invoke.png` | `01-invoke-1.txt`, `02-invoke-2.txt` |
| `start-api` + 3 curls (sem warm) | `start-api-curls.png` | `03-start-api-curls.txt` |
| `--warm-containers LAZY` + 3 curls | `warm-containers.png` | `04-warm-containers.txt` |
| Timeout 3 s (erro) | `timeout-erro.png`, `timeout-erro01.png` | `05-timeout-erro.txt` |
| Timeout 10 s (ok) | `timeout-10-ok.png` | `06-timeout-10-ok.txt` |
| Erro 400 | — | `07-erro-400.txt` |

## Resultados observados

| Experimento | Resultado |
|---|---|
| `sam local invoke` (1ª vez) | Duration 59,87 ms · Init Duration 0,05 ms · tempo total 45,78 s (inclui o build da imagem Docker, que ainda não existia localmente) · `invocacaoNesteAmbiente`: 1 |
| `sam local invoke` (2ª vez) | Duration 49,83 ms · Init Duration 0,03 ms · tempo total 9,41 s (imagem já em cache) · `invocacaoNesteAmbiente`: 1 · outro `SAM_CONTAINER_ID` |
| `start-api` sem `--warm-containers`, 3 chamadas | `invocacaoNesteAmbiente`: 1, 1, 1 |
| `start-api --warm-containers LAZY`, 3 chamadas | `invocacaoNesteAmbiente`: 1, 2, 3 |
| `demorar: true` com Timeout 3 | HTTP 502 (`{"message":"Internal server error"}`); log: `Function 'GuiaTransporteFunction' timed out after 3 seconds`, Duration 3000 ms |
| `demorar: true` com Timeout 10 | HTTP 201, resposta em ~9,4 s (5 s de sleep + subida do container) |
| body sem `requisicaoId` | HTTP 400 `{"erro": "requisicaoId obrigatório"}` |

## Respostas

**1. Por que a primeira invocação demorou mais que a segunda? O que acontece na fase de Init?**
Na fase de Init a plataforma cria o ambiente de execução (no SAM local, sobe um container), inicia o runtime Python e executa o código que fica fora do handler (os imports e `contador = 0`). Só depois o handler roda. Isso é o cold start.
No `sam local invoke`, porém, cada chamada sobe um container novo: as duas invocações retornaram `invocacaoNesteAmbiente` = 1 e o `SAM_CONTAINER_ID` foi diferente, ou seja, as duas passaram pelo Init. A diferença de tempo (45,78 s contra 9,41 s) veio de a primeira ter de construir a imagem Docker local (`Local image was not found... Building image`), não de reaproveitamento de ambiente. O Init Duration que o emulador reporta é praticamente zero nas duas (0,05 ms e 0,03 ms), então ele não mostra o custo real do cold start; no Lambda na nuvem esse valor aparece bem maior nos logs. A diferença entre cold e warm só fica visível quando o ambiente é reaproveitado (pergunta 2).

**2. O que o campo `invocacaoNesteAmbiente` mostrou com e sem `--warm-containers`? O que isso diz sobre guardar estado numa variável global?**
Sem `--warm-containers`: 1, 1, 1 (container novo a cada chamada, a variável volta a 0). Com `--warm-containers LAZY`: 1, 2, 3 (o container é reaproveitado e a variável sobrevive). Portanto a variável global só persiste enquanto o ambiente for reaproveitado, e a plataforma não garante isso: o ambiente pode ser descartado a qualquer momento, e várias instâncias em paralelo teriam cada uma o seu contador. Estado que precisa persistir ou ser compartilhado deve ficar fora da função (banco de dados, cache, armazenamento externo). A variável global serve, no máximo, como cache descartável.

**3. O que aconteceu com `demorar = true`? Qual é o tempo máximo de uma execução no Lambda e o que fazer com um trabalho mais longo?**
A função dorme 5 s, mas o Timeout do template era 3 s; a plataforma interrompeu a execução aos 3000 ms e, como não houve resposta válida, o `start-api` devolveu HTTP 502. Com Timeout 10 (e `sam build` de novo) a mesma chamada terminou e respondeu 201. O máximo de uma execução no Lambda é 15 minutos (900 s) ([Cotas do Lambda](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)). Trabalho mais longo deve ser dividido em etapas menores (por exemplo, com filas e várias funções) ou ir para um serviço sem esse limite, como containers (ECS/Fargate) ou VMs.

**4. Custo de 1 milhão de execuções com 128 MB e 100 ms (us-east-1)**

- Requisições: 1.000.000 × US$ 0,20 / 1.000.000 = **US$ 0,20**
- Computação: 128 MB = 0,125 GB; 100 ms = 0,1 s
  - GB-s = 1.000.000 × 0,125 GB × 0,1 s = **12.500 GB-s**
  - 12.500 × US$ 0,0000166667 = **US$ 0,2083**
- **Total ≈ US$ 0,41** (0,20 + 0,2083 = 0,4083), antes da faixa gratuita.

**5. Em que parte do Rota Vital uma função assim faria sentido, e em qual não faria?**
Faz sentido em tarefas curtas, sem estado e acionadas por evento ou com demanda irregular: gerar a guia de transporte quando uma requisição é criada, validar o pedido, enviar notificações. Paga-se só pelo uso e a escala acompanha picos. Não faria sentido onde há conexão contínua ou estado em memória, como o rastreamento em tempo real de uma entrega (conexões abertas, atualizações frequentes); em processamentos acima do limite de tempo; em componentes que exigem latência previsível sem cold start; nem no banco de dados do sistema.

## Uso de IA

- **Claude (Anthropic):** apoio na estrutura do projeto SAM, no `template.yaml`, no rascunho do README e do roteiro do vídeo, e na revisão do repositório contra a rubrica da atividade.
- **Como validei:** executei eu mesmo os comandos (`sam build`, `sam local invoke`, `sam local start-api`, `curl`) no meu Mac, e os prints em `evidencias/` são do meu terminal. Conferi as respostas contra as saídas observadas (contador 1,1,1 × 1,2,3; erro de timeout aos 3 s; 201 com Timeout 10), refiz a conta de custo à mão e consultei a documentação de cotas do Lambda para o limite de 15 minutos. Consigo explicar o código do `app.py` e do `template.yaml` em sala.

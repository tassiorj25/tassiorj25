# Instalar o Blueprint em outro projeto

As skills precisam estar **dentro** do projeto onde você vai trabalhar (ex.: o
alpha hub), numa pasta `.claude/skills/`, com as `tools/` na raiz. Há duas
formas.

## Opção 1 — bootstrap de uma linha (recomendado)

Cole isto num terminal **dentro do projeto do alpha hub** (ou peça para o Claude
da conversa "Engenharia Reversa" rodar):

```sh
tmp=$(mktemp -d) && \
git clone --branch claude/ecstatic-bohr-nsh7ld --depth 1 \
  https://github.com/tassiorj25/tassiorj25 "$tmp" && \
sh "$tmp/install.sh" . && \
rm -rf "$tmp"
```

Isso copia as sete skills para `.claude/skills/bp-*` e as ferramentas para
`tools/`. Depois, para a etapa de captura:

```sh
npm install playwright && npx playwright install chromium
```

## Opção 2 — clonar e rodar o instalador

```sh
git clone --branch claude/ecstatic-bohr-nsh7ld \
  https://github.com/tassiorj25/tassiorj25 blueprint
sh blueprint/install.sh /caminho/do/alpha-hub
```

## Confirmar que carregou

Numa sessão do Claude Code aberta no projeto do alpha hub, as skills aparecem
como `bp-recon`, `bp-tokens`, … Para usar, basta pedir em linguagem natural:

```
use bp-recon no https://alvo-do-alpha-hub.example
```

e seguir o pipeline: `recon → tokens → model → spec → build → verify → brand`.

## O que fica onde

O Blueprint grava tudo numa pasta `blueprint/` no projeto — evidências,
tokens, specs, pontuações. Essa pasta é material de trabalho do alpha hub, não
deste repositório. Se não quiser versioná-la, adicione `blueprint/` ao
`.gitignore` do alpha hub.

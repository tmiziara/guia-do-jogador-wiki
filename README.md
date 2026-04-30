# Guia do Jogador Wiki

Projeto simples em MkDocs para publicar `C:\Users\Tiagin\Desktop\RPG\Thyrmhald-Vault\Guia do Jogador` como wiki estática.

## Uso

1. Atualizar as notas importadas:

```powershell
python .\scripts\sync_wiki.py
```

2. Rodar localmente:

```powershell
python -m mkdocs serve
```

3. Gerar site estático:

```powershell
python -m mkdocs build
```

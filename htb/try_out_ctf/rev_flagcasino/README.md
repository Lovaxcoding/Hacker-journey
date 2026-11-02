# README.md — Writeup « Robo Casino » (HTB Reverse)


# HTB — Robo Casino

> **Catégorie** : Reverse Engineering  
> **Difficulté** : Easy  
> **Plateforme** : Hack The Box  
> **Flag** : `HTB{r4nd_1s_v3ry_REDACTABLE}`

---

## Contexte

Un binaire Linux x86-64 simule un « Robo Casino ». Le programme demande une série de paris (un par ligne) et vérifie chacun contre une valeur secrète. Un mauvais pari déclenche le système de sécurité et termine immédiatement le processus.

```text
[ ** WELCOME TO ROBO CASINO **]
     ,     ,
    (\____/)
     (_oo_)
       (O)
     __||__    \)
  []/______\[] /
  / \______/ \/
 /    /__\
(\   /____\
---------------------
[*** PLEASE PLACE YOUR BETS ***]
>
```

Le binaire est fourni sans source. On commence donc par une reconnaissance classique (checksec, strings, Ghidra).

---

## Reconnaissance

```bash
file casino
checksec --file=casino
```

Résultat :

| Protection | État |
|---|---|
| Arch | amd64-64-little |
| RELRO | Partial |
| Stack canary | **No** |
| NX | Enabled |
| PIE | Enabled |

Pas de canary, PIE activé : rien de bloquant pour du reverse statique.

Un coup de `strings` ne révèle pas le flag directement, on passe donc par Ghidra pour décompiler `main`.

---

## Analyse du binaire

Le pseudo-code décompilé de `main` est sans ambiguïté :

```c
int main(void)
{
  int random_var;
  char input;
  uint i;

  puts("[ ** WELCOME TO ROBO CASINO **]");
  puts("...");
  puts("[*** PLEASE PLACE YOUR BETS ***]");

  i = 0;
  while (true) {
    if (0x1c < i) {                                    // 28 < i → fin
      puts("[ ** HOUSE BALANCE $0 - PLEASE COME BACK LATER ** ]");
      return 0;
    }
    printf("> ");
    random_var = __isoc99_scanf(&DAT_001020fc, &input);
    if (random_var != 1) break;

    srand((int)input);                                 // ← le seed
    random_var = rand();
    if (random_var != *(int *)(check + (long)(int)i * 4)) {
      puts("[ * INCORRECT * ]");
      puts("[ *** ACTIVATING SECURITY SYSTEM - PLEASE VACATE *** ]");
      exit(-2);
    }
    puts("[ * CORRECT *]");
    i = i + 1;
  }
  exit(-1);
}
```

### Ce qu'il faut retenir

- La boucle tourne **29 fois** (`i = 0` à `28`, condition `0x1c < i`).
- À chaque itération, le programme :
  1. lit un caractère dans `input` (`char`)
  2. initialise le PRNG avec `srand((int)input)`
  3. tire un `rand()`
  4. compare ce tirage à `check[i]` (tableau hardcodé dans l'ELF)
  5. sort en `exit(-2)` si la comparaison échoue
- Le tableau `check[]` contient les **valeurs attendues** pour les 29 itérations.

---

## La faille : `srand()` + `rand()` est déterministe

`srand()` et `rand()` forment un **générateur pseudo-aléatoire** (PRNG) : la séquence produite par `rand()` dépend **entièrement** du seed passé à `srand()`.

Deux problèmes majeurs se cumulent ici :

1. **Le seed est contrôlé par l'utilisateur** et tient sur un **seul octet** (`char input`). Il n'y a donc que **256 valeurs possibles**.
2. **Les valeurs attendues sont hardcodées** dans le binaire (`check[]`), donc lisibles statiquement.

Conséquence : pour chaque `i`, il suffit de brute-forcer les 256 seeds possibles, de calculer `srand(s); rand()` et de comparer à `check[i]`. La complexité totale est de **29 × 256 = 7 424 appels** à `rand()`, soit **moins d'une milliseconde** sur une machine moderne.

---

## Extraction du tableau `check[]`

Trois méthodes équivalentes :

**Ghidra** : `Symbol Tree → check` puis lecture de la vue mémoire.

**objdump** :

```bash
readelf -s ./casino | grep check
objdump -s -j .data ./casino
```

**pwntools (le plus rapide)** :

```python
from pwn import *
elf = ELF("./casino", checksec=False)
addr = elf.symbols["check"]
check = [int.from_bytes(elf.read(addr + i*4, 4), "little", signed=True)
         for i in range(29)]
```

---

## Résolution

### Script final

```python
#!/usr/bin/env python3
"""
exploit.py — HTB Reverse « Robo Casino »

Le programme fait srand((int)input); rand(); compare à check[i].
Les seeds trouvés correspondent aux codes ASCII du flag :
  72 84 66 123 ... = "HTB{..."

Le scanf lit un CARACTÈRE (%c), pas un entier :
il faut donc envoyer directement le flag en octets bruts.
"""

import re
from ctypes import CDLL, c_uint, c_int
from pwn import *

BIN = "./casino"
N   = 29

context.binary = elf = ELF(BIN, checksec=False)

libc = CDLL("libc.so.6")
libc.srand.argtypes = [c_uint]
libc.rand.restype  = c_int

# 1. Extraire check[] et brute-forcer les seeds
check_addr = elf.symbols["check"]
check = [int.from_bytes(elf.read(check_addr + i*4, 4), "little", signed=True)
         for i in range(N)]

def find_seed(expected):
    for seed in range(256):
        signed = seed if seed < 128 else seed - 256
        libc.srand(signed & 0xFFFFFFFF)
        if libc.rand() == expected:
            return signed
    return None

seeds = [find_seed(v) for v in check]
assert all(s is not None for s in seeds)
log.success(f"Seeds (ASCII) : {bytes([s & 0xFF for s in seeds])!r}")

# 2. Envoyer les seeds sous forme d'octets bruts (format %c)
p = process(["stdbuf", "-o0", BIN])
p.recvuntil(b"BETS ***]\n")

for s in seeds:
    p.send(bytes([s & 0xFF]))      # 1 caractère par itération
    p.recvuntil(b"CORRECT")

output = p.recvall(timeout=3).decode(errors="replace")
print(output)

m = re.search(r"HTB\{[^}]+\}", output)
if m:
    log.success(f"FLAG : {m.group(0)}")
```

### Sortie

```text
[*] check[0..4] = ['0x244b28be', '0xaf77805', '0x110dfc17', '0x7afc3a1', '0x6afec533']
[+] Seeds (ASCII) : b'HTB{r4nd_1s_v3ry_REDACTABLE}'
[+] FLAG : HTB{r4nd_1s_v3ry_REDACTABLE}
```

Le flag lui-même résume le challenge : *« rand is very predictable »*.

---

## Pièges rencontrés

### 1. `char` signé

Sur x86-64 Linux, `char` est **signé**. Un `input` de `0x80` vaut `-128`, donc `srand((unsigned)(-128)) = srand(4294967168)`. Il faut reproduire cette conversion dans le script :

```python
signed = seed if seed < 128 else seed - 256
libc.srand(signed & 0xFFFFFFFF)
```

### 2. `srand(0) == srand(1)` sur glibc

Quirk connu de la libc GNU : les seeds 0 et 1 produisent la même séquence. Non bloquant ici, mais bon à savoir.

### 3. Format `scanf`

Le décompilé montre `__isoc99_scanf(&DAT_001020fc, &input)` sans préciser le format. Trois cas possibles :

| Format | Interprétation | Envoi correct |
|---|---|---|
| `%hhd` | entier décimal signé | `str(seed)` |
| `%c` | **caractère brut** ⭐ | `bytes([seed & 0xFF])` |
| `%d` | 4 octets (buffer overflow) | `p32(seed)` |

Ici, c'était **`%c`**. L'indice décisif : les seeds brute-forcés tombent tous dans la plage ASCII imprimable (32–126) et forment une chaîne lisible. Quand c'est le cas, on envoie les **octets bruts**, pas les nombres.

### 4. Buffering stdout

```c
printf("> ");   // pas de '\n'
```

Sur un pipe (pas de TTY), glibc utilise le **buffering par blocs** : `> ` reste dans le buffer et n'apparaît jamais avant la fin du programme. `recvuntil(b"> ")` bloque donc indéfiniment.

Solution : lancer le binaire via `stdbuf -o0` (stdout non-bufferisé) ou `process(..., pty=True)`.

```python
p = process(["stdbuf", "-o0", BIN])
```

---

## Décodage du flag

```
HTB{r4nd_1s_REDACTABLE}
```

| Leet | Sens |
|---|---|
| `r4nd` | rand |
| `1s` | is |
| `v3ry` | very |
| `pr3d1ct4bl3` | predictable |

→ **"rand is very predictable"**

Le flag décrit exactement la faille exploitée : un PRNG non cryptographique avec un seed contrôlé et un espace de 256 valeurs, c'est une porte grande ouverte.

---

## Leçons retenues

- **`srand()` / `rand()` ne sont pas cryptographiques** : ce sont des PRNG déterministes conçus pour la simulation, jamais pour la sécurité. Ne jamais les utiliser pour générer un secret.
- **Un seed de 8 bits = 256 possibilités** : espace de recherche ridicule, brute-forçable en quelques microsecondes.
- **Un seed contrôlé par l'utilisateur est une faille** : si l'attaquant peut fixer le seed, il peut prédire la sortie et inverser toute vérification.
- **Les valeurs hardcodées sont réversibles** : le tableau `check[]` est dans le binaire, lisible avec `objdump` / Ghidra. La sécurité par l'obscurité ne résiste pas au reverse engineering.
- **Toujours vérifier le format `scanf`** : `%d` dans un `char` est un buffer overflow potentiel — un second chemin d'exploitation possible.
- **La libc compte** : `rand()` dépend de l'implémentation. Toujours utiliser la même libc que la cible pour reproduire la séquence.
- **Le buffering stdout est un piège classique** : `printf` sans `\n` sur pipe = block-buffered → utiliser `stdbuf -o0` ou `pty=True`.

---

## Outils utilisés

- **Ghidra** — décompilation et extraction du tableau `check`
- **`objdump`**, **`readelf`** — inspection rapide des sections et symboles
- **`gdb`** — débogage, dump mémoire en runtime
- **`pwntools`** — scripting d'exploitation, extraction de symboles ELF
- **`ctypes.CDLL("libc.so.6")`** — reproduction exacte de `srand` / `rand` en Python

---

## Références

- [`srand(3)` — man page](https://man7.org/linux/man-pages/man3/srand.3.html)
- [`rand(3)` — man page](https://man7.org/linux/man-pages/man3/rand.3.html)
- [pwntools documentation](https://docs.pwntools.com/)
- [Ghidra](https://ghidra-sre.org/)


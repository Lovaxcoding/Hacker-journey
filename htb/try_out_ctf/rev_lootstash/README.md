# Writeup – HTB Reverse « Diving into the stash »

## Contexte

Un binaire Linux x86-64 qui simule une plongée dans un « stash » (une réserve). Le programme affiche un message, attend un peu, puis sélectionne aléatoirement un élément dans un tableau `gear[]` :

```text
Diving into the stash - let's see what we can find.
.....
You got: '<élément aléatoire>'. Now run, before anyone tries to steal it!
```

Le décompilé de `main` est le suivant :

```c
int main(void)
{
  int iVar1;
  time_t tVar2;
  int i;

  setvbuf(stdout, NULL, 2, 0);
  tVar2 = time(NULL);
  srand((uint)tVar2);              // ← seed = timestamp courant

  puts("Diving into the stash - let's see what we can find.");
  for (i = 0; i < 5; i = i + 1) {
    putchar('.');
    sleep(1);
  }

  iVar1 = rand();
  printf("\nYou got: '%s'. Now run, before anyone tries to steal it!\n",
         (&gear)[(int)((ulong)(long)iVar1 % 0x7f8 >> 3)]);
  return 0;
}
```

## Analyse

### Ce que fait le programme

1. **`setvbuf(stdout, NULL, 2, 0)`** — désactive le buffering de stdout (`_IONBF = 2`). Détail utile : les `putchar('.')` et le `printf` apparaissent immédiatement, pas de deadlock pwntools.
2. **`srand(time(NULL))`** — le seed est **le timestamp courant**, en secondes. Le PRNG est donc prévisible : si on connaît l'heure d'exécution (à ±1 seconde près), on peut prédire `rand()`.
3. **5 `putchar('.')` + `sleep(1)`** — 5 secondes d'attente, probablement pour rendre l'exploit moins évident et inciter à l'analyse.
4. **`rand() % 0x7f8 >> 3`** — l'indice dans `gear[]` est calculé ainsi :
   - `rand() % 0x7f8` : reste modulo `0x7f8 = 2040`
   - `>> 3` : division entière par 8
   - Plage résultante : `0` à `254` (soit **255 valeurs possibles**)
5. **`(&gear)[index]`** — le tableau `gear[]` est un tableau de **pointeurs** (`char *`), chaque entrée pointant vers une chaîne (probablement 8 octets par entrée sur x86-64). Le décalage `>> 3` confirme : chaque élément fait **8 octets** (taille d'un pointeur 64 bits).

### La faille : le flag est dans le binaire

Le programme sélectionne **aléatoirement** une chaîne dans `gear[]` et l'affiche. Mais toutes les chaînes de `gear[]` sont **hardcodées dans le binaire**, y compris le flag. Inutile de brute-forcer le seed ou de prédire `rand()` : il suffit de **lire le binaire** pour extraire toutes les chaînes, et le flag y est en clair.

L'utilisateur a trouvé le flag directement dans la section `.rodata` à l'adresse `0x103c50` :

```
00103c50  48 54 42 7b 6e 33 33 64 6c 33 5f 31 6e 5f 61 5f  HTB{n33dl3_1n_a_l
00103c60  6c 30 30 74 5f 73 74 61 63 6b 7d                 REDACTED}
```

Soit :

```
HTB{n33dl3_1n_a_REDACTED}
```

## Résolution

### Méthode 1 — `strings` (la plus rapide)

```bash
strings -a ./stash | grep -i HTB
```

Résultat :

```
HTB{n33dl3_1n_a_l00t_stack}
```

C'est la méthode la plus directe : le flag est dans `.rodata`, `strings` le sort en une seconde.

### Méthode 2 — Ghidra / désassembleur

1. Ouvrir le binaire dans Ghidra
2. Dans la fenêtre **Symbol Tree → Strings**, chercher `HTB`
3. Double-cliquer sur le flag → Ghidra montre la chaîne et ses XREF
4. Une XREF mène au tableau `gear[]` dans `main` — le flag est une des entrées possibles

L'utilisateur a fait exactement cela : il a repéré l'adresse `0x103c50` avec une XREF vers `0x107368` (probablement l'adresse de `gear[]` + offset).

### Méthode 3 — Extraction du tableau `gear[]` avec pwntools

Si on veut être rigoureux et lister **toutes** les chaînes possibles (pas seulement le flag) :

```python
from pwn import *

elf = ELF("./stash", checksec=False)

# Trouver l'adresse de gear[] (symbole ou via Ghidra)
gear_addr = elf.symbols.get("gear")
if gear_addr is None:
    # Pas de symbole : chercher manuellement dans .data / .rodata
    # ou via les XREF dans Ghidra
    print("gear non symbolisé — utiliser Ghidra")
else:
    for i in range(255):
        ptr = u64(elf.read(gear_addr + i*8, 8))
        if ptr == 0:
            break
        s = elf.read(ptr, 64).split(b"\x00")[0]
        print(f"gear[{i:3d}] = {s.decode(errors='replace')}")
```


## Décodage du flag

```
HTB{n33dl3_1n_a_REDACTED}
```

| Leet | Sens |
|---|---|
| `n33dl3` | needle |
| `1n` | in |
| `a` | a |
| `REDACTED` | loot |
| `REDACTED` | stack |

→ **"needle in a loot stack"**

Une référence à l'expression « needle in a haystack » (aiguille dans une botte de foin), adaptée au thème du challenge : trouver le flag parmi les nombreuses chaînes de `gear[]`, c'est chercher une aiguille dans une pile de butin.

## Flag

```
HTB{REDACTED}
```

## Pièges et particularités

### 1. Le `rand()` est un leurre

Le programme utilise `srand(time(NULL))` et `rand()` pour sélectionner une chaîne — mais **toutes les chaînes sont dans le binaire**. Le « hasard » ne protège rien : le flag est statiquement extractible. C'est un classique du reverse : ne pas se laisser distraire par la logique d'exécution quand les données sont en clair dans le binaire.

### 2. `setvbuf(stdout, NULL, 2, 0)` — pas de deadlock pwntools

Contrairement à « Robo Casino » où `printf("> ")` sans `\n` bloquait sur pipe, ici `setvbuf` désactive explicitement le buffering (`_IONBF`). Les `putchar('.')` et le `printf` final s'affichent immédiatement. Pas besoin de `stdbuf -o0` ni de `pty=True`.

### 3. Le `sleep(1)` × 5

Le programme attend 5 secondes avant d'afficher le résultat. Ce n'est pas une protection — c'est juste une mise en scène. Un exploit qui lit le binaire n'a même pas besoin d'exécuter le programme.

### 4. `>> 3` = tableau de pointeurs 64 bits

Le décalage `>> 3` (division par 8) sur l'indice confirme que `gear[]` est un tableau de **pointeurs** (`char *`), chaque entrée faisant 8 octets sur x86-64. L'indice final est dans `[0, 254]`, soit 255 chaînes possibles.

## Leçons retenues

- **Le flag hardcodé dans le binaire est extractible statiquement** : `strings`, `objdump -s -j .rodata`, ou Ghidra suffisent. Ne jamais se laisser distraire par la logique d'exécution (ici `rand()`) quand les données sont en clair.
- **`srand(time(NULL))` est prévisible** : le seed est le timestamp courant, devinable à ±1 seconde. Un PRNG non cryptographique avec un seed temporel n'offre aucune sécurité.
- **Un `rand()` qui sélectionne parmi des chaînes hardcodées ne cache rien** : toutes les chaînes sont dans `.rodata`, y compris celle qu'on cherche.
- **`strings | grep HTB`** est souvent la première commande à lancer sur un binaire de challenge reverse — elle résout une bonne partie des challenges « easy » en quelques secondes.
- **`setvbuf(stdout, NULL, _IONBF, 0)`** désactive le buffering : pas de deadlock pwntools, contrairement aux `printf` sans `\n`.

## Outils recommandés

- **`strings`** — extraction rapide des chaînes imprimables
- **Ghidra** — décompilation, XREF, vue `.rodata`
- **`objdump -s -j .rodata`** — dump hexadécimal de la section des données en lecture seule
- **pwntools** — extraction programmatique du tableau `gear[]` si on veut lister toutes les chaînes
- **`ctypes.CDLL("libc.so.6")`** — reproduction de `srand`/`rand` pour vérifier la prédictibilité

---

Le challenge est un excellent contre-exemple pédagogique : il **simule** une complexité (PRNG, sleep, sélection aléatoire) pour détourner l'attention, alors que le flag est en clair dans le binaire. 🧵

# Writeup – HTB Hardware « Critical Flight »

##  Contexte

On nous fournit une archive `hw_critical_flight.zip`. Après décompression, on obtient un dossier `flight_control_board/` contenant une série de fichiers **Gerber** (`.gbr`) — les fichiers de fabrication d'un PCB (circuit imprimé) générés par KiCad.

```bash
unzip hw_critical_flight.zip
ls flight_control_board/
```

**Sortie :**

```
HadesMicro-B_Cu.gbr          HadesMicro-F_Cu.gbr
HadesMicro-B_Fab.gbr         HadesMicro-F_Fab.gbr
HadesMicro-B_Mask.gbr        HadesMicro-F_Mask.gbr
HadesMicro-B_Paste.gbr       HadesMicro-F_Paste.gbr
HadesMicro-B_Silkscreen.gbr  HadesMicro-F_Silkscreen.gbr
HadesMicro-Edge_Cuts.gbr     HadesMicro-In1_Cu.gbr
                             HadesMicro-In2_Cu.gbr
```

>  **Piège classique** : l'archive contient aussi un dossier `__MACOSX/` avec des fichiers `._HadesMicro-*.gbr`. Ce sont des **métadonnées macOS** (resource forks), **pas** les vrais Gerber. Il faut les ignorer / les supprimer.

```bash
rm -rf __MACOSX
find flight_control_board -name '._*' -delete
```

##  Comprendre les fichiers Gerber

Un PCB est constitué de plusieurs **couches** empilées. Chaque fichier `.gbr` correspond à une couche :

| Fichier | Rôle |
|---|---|
| `F_Cu` / `B_Cu` | Cuivre face avant / arrière |
| `In1_Cu` / `In2_Cu` | **Couches internes de cuivre**  |
| `F_Silkscreen` / `B_Silkscreen` | Sérigraphie (texte, logo) |
| `F_Mask` / `B_Mask` | Masque de soudure (vernis) |
| `F_Paste` / `B_Paste` | Pâte à braser |
| `F_Fab` / `B_Fab` | Couche de fabrication |
| `Edge_Cuts` | Contour de la carte |

Le format Gerber est du **texte vectoriel** (RS-274X) : pas directement lisible, il faut le **rendre en image**.

## 🔍 Analyse

### Rendu graphique

On utilise `gerbv` (ou KiCad Gerber Viewer, ou [tracespace.io](https://tracespace.io/view/)) :

```bash
gerbv flight_control_board/*.gbr
```

Ou en export PNG par couche :

```bash
mkdir -p out
for f in flight_control_board/*.gbr; do
  base=$(basename "$f" .gbr)
  gerbv -x png -o "out/${base}.png" -b "#000000" -f "#FFFFFF" "$f"
done
```

### Où chercher ?

Sur ce challenge, le flag est **découpé en deux morceaux** :

1. **Première partie** → sur `HadesMicro-B_Cu.gbr` (cuivre, **face arrière**).

   >  La face arrière est vue par transparence depuis le dessous : il faut **miroiter** l'image.

   ```bash
   convert out/HadesMicro-B_Cu.png -flop out/back_cu_flop.png
   ```

2. **Deuxième partie** → sur `HadesMicro-In1_Cu.gbr` (une **couche interne** de cuivre).

   > C'est la cachette typique : on regarde souvent le dessus (`F_*`) et le dessous (`B_*`), mais **on oublie les couches internes**.

## 🚀 Exploitation

On assemble les deux morceaux trouvés sur les couches :

- `B_Cu` → `533_7h3_1nn32_w02k1n95_0f_` (ou début)
- `In1_Cu` → la suite de la chaîne

Le flag final, en leet speak :

```
HTB{REDACTED}
```

## 🔓 Décodage du leet speak

| Leet | Sens |
|---|---|
| `533` | see |
| `7h3` | the |
| `1nn32` | inner |
| `w02k1n95` | workings |
| `0f` | of |
| `REDACTED` | electronics |

→ **"See the inner workings of electronics"**

Un jeu de mot parfait pour un challenge où il faut littéralement regarder **à l'intérieur** (couches internes) du circuit. 🔬

## 🏁 Flag

```
HTB{REDACTED}
```

##  Leçons retenues

- Les archives macOS contiennent `__MACOSX/` avec des fichiers `._*` — ce sont des pièges à **ignorer systématiquement**.
- Les fichiers Gerber sont **multi-couches** : ne jamais se limiter à la sérigraphie ou à la face avant. Les couches internes (`In1_Cu`, `In2_Cu`) et la face arrière (`B_*`) sont les cachettes classiques.
- **Face arrière = image miroir** : penser à `-flop` (ImageMagick) ou à un flip horizontal dans gerbv.
- **Astuce rapide** : si un outil écrit du texte en clair, un `strings *.gbr | grep -i htb` peut parfois suffire — mais le rendu graphique reste la méthode fiable.
- Lire le flag à voix haute / le décoder en leet aide à repérer les erreurs de transcription (caractères parasites comme `#$@` à la fin sont souvent des décorations du PCB et **ne font pas partie du flag**).

##  Outils recommandés

- **`gerbv`** — visualisation et export PNG des Gerber
- **KiCad** — Gerber Viewer graphique
- **[tracespace.io/view](https://tracespace.io/view/)** — visualiseur en ligne, pratique pour superposer / isoler les couches
- **ImageMagick** (`convert -flop`) — miroir des faces arrière
- **`strings`**, **`grep`**, **`head`** — inspection rapide du contenu texte

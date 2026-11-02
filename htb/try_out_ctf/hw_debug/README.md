# Writeup – HTB Hardware « Debug »

## Contexte

On dispose d'un fichier `hw_debug.sal`. Une reconnaissance rapide révèle qu'il s'agit en réalité d'une archive ZIP :

```bash
file hw_debug.sal
# hw_debug.sal: Zip archive data, at least v2.0 to extract, compression method=deflate
```

Le fichier `.sal` est une **capture Saleae Logic** (analyseur logique). Saleae Logic 2 sauvegarde ses captures dans une archive ZIP contenant les données brutes des canaux numériques et analogiques, ainsi que les métadonnées de la capture. Le nom du challenge (« hw_debug ») suggère une **console de debug** — un classique du reverse hardware.

## Analyse

### Extraction de l'archive

```bash
unzip hw_debug.sal -d hw_debug
ls -la hw_debug/
```

Contenu :

```
digital-0.bin   (88 610 octets)
digital-1.bin   (178 171 octets)
meta.json
```

- `meta.json` : métadonnées de la capture (fréquence d'échantillonnage, canaux actifs, noms des canaux)
- `digital-X.bin` : données brutes du canal numérique `X`

### Lecture des métadonnées

```bash
jq . meta.json
```

Les informations essentielles :

| Champ | Valeur | Interprétation |
|---|---|---|
| `connectedDevice.name` | `Logic 8` | Analyseur Saleae Logic 8 |
| `sampleRate.digital` | `25 000 000` | **25 MHz** — fréquence d'échantillonnage |
| `enabledChannels` | `Digital 0`, `Digital 1` | Seulement 2 canaux actifs |
| `rowsSettings[0].name` | **`TX`** (Digital 0) | Ligne de transmission |
| `rowsSettings[1].name` | **`RX`** (Digital 1) | Ligne de réception |
| `captureProgress.maxCollectedTime` | `37.47 s` | Durée réelle de la capture |

**Conclusion immédiate** : deux canaux nommés `TX` et `RX` sur un analyseur logique, c'est du **UART** (port série asynchrone). Le nom du challenge (« debug ») confirme qu'il s'agit d'une **console de debug série**.

## Exploitation

### Méthode 1 — Saleae Logic 2 (recommandée)

1. Rendre l'AppImage exécutable et la lancer :

   ```bash
   chmod +x Logic-2.4.48-linux-x64.AppImage
   ./Logic-2.4.48-linux-x64.AppImage --appimage-extract-and-run
   ```

2. **File → Open Capture…** → sélectionner `hw_debug.sal`

3. Cliquer sur l'icône **`+`** à côté de **Analyzers** → choisir **Async Serial**

4. Configurer le décodeur :

   | Paramètre | Valeur |
   |---|---|
   | Input channel | `RX` (canal 1) |
   | Bit Rate (bps) | `115200` |
   | Bits per frame | `8` |
   | Parity | `None` |
   | Stop bits | `1` |
   | Signal inversion | `No` |

5. Les données décodées apparaissent dans le panneau inférieur.

### Méthode 2 — sigrok / PulseView (libre)

```bash
sudo apt install pulseview sigrok-cli
pulseview hw_debug.sal
```

Ou en ligne de commande :

```bash
sigrok-cli -i hw_debug.sal -P uart:rx=D1:baudrate=115200 -A uart=rx_data
```

Pour tester plusieurs baudrates d'un coup :

```bash
for br in 9600 19200 38400 57600 115200 230400; do
  echo "=== $br bauds ==="
  sigrok-cli -i hw_debug.sal -P uart:rx=D1:baudrate=$br -A uart=rx_data 2>/dev/null | head -5
done
```

### Méthode 3 — Estimation manuelle du baudrate

À 25 MHz, la correspondance baudrate ↔ échantillons par bit est :

| Baudrate | Samples/bit | Usage typique |
|---|---|---|
| 9600 | 2604 | Console lente, industriel |
| 57600 | 434 | Debug intermédiaire |
| **115200** | **217** | **Console de debug standard** |
| 230400 | 108.5 | Debug rapide |

On commence toujours par **115200**, le standard de fait des consoles embarquées.

## Résolution

### Paramètres retenus

| Élément | Valeur |
|---|---|
| Protocole | UART (Async Serial) |
| Canal | **RX** (canal 1) |
| Baudrate | **115200** bauds |
| Bits / parité / stop | 8 / None / 1 |

### Piège rencontré

`meta.json` nommait les canaux `TX` (canal 0) et `RX` (canal 1). Le flux exploitable se trouvait sur **RX**, pas sur TX. Sur un bus UART, TX et RX sont croisés : selon le point de mesure (côté émetteur ou côté récepteur), le flux utile peut être sur l'un ou l'autre. **Il faut toujours tester les deux canaux.**

### Données réparties sur plusieurs trames

Le flag était **divisé en plusieurs trames** dans le flux UART. En UART, les données sont envoyées par paquets de quelques octets avec des pauses — il faut donc **concaténer les morceaux décodés dans l'ordre chronologique** pour reconstituer la chaîne complète.

## Flag

```
HTB{REDACTED}
```

### Décodage du leet speak

| Leet | Sens |
|---|---|
| `547311173` | satellite |
| `n37w02k` | network |
| `REDACTED` | compromised |

→ **"satellite network compromised"**

Un flag cohérent avec le thème du challenge : on a espionné la console de debug série d'un système embarqué (probablement un module de communication satellite) et découvert que son réseau avait été compromis.

## Leçons retenues

- Un fichier `.sal` n'est **qu'une archive ZIP** : `unzip` + `jq meta.json` donne immédiatement le protocole (via les noms de canaux) et la fréquence d'échantillonnage.
- Les noms de canaux (`TX`, `RX`) sont un **indice direct** sur le protocole : c'est de l'UART.
- Le **baudrate** est le paramètre critique — toujours essayer `115200` en premier, puis `9600`.
- **Toujours tester les deux canaux** : TX et RX sont croisés sur un bus UART, le flux utile peut être sur l'un ou l'autre.
- Les données UART sont souvent **réparties sur plusieurs trames** : il faut concaténer les morceaux décodés dans l'ordre.
- Le format `.bin` de Logic 2 est compressé par transitions : ne pas tenter de le lire brut avec `numpy`, passer par les outils officiels.
- **Saleae Logic 2** et **PulseView** décodent automatiquement UART, SPI, I²C, SWD, JTAG — ne pas réinventer la roue.

## Outils recommandés

- **Saleae Logic 2** — ouverture native `.sal`, décodeurs intégrés (AppImage Linux)
- **PulseView / sigrok-cli** — alternative libre, support `.sal` natif depuis sigrok 0.5.2
- **`jq`** — inspection rapide de `meta.json` (indispensable)
- **`unzip`**, **`file`** — reconnaissance initiale du fichier

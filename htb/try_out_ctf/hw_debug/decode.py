import numpy as np

# Lire le canal (format Saleae Logic 2 : encodage par transitions)
data = np.fromfile("digital-0.bin", dtype=np.uint8)
print("Octets lus:", len(data))

# Le format .bin de Logic 2 est compressé (RLE / transitions),
# donc une lecture brute ne donne pas directement le signal.
# → passer par Logic 2 ou PulseView pour la reconstruction.

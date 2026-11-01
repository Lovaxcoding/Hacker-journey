Writeup – HTB : Hardware "It's Oops PM"
 Contexte

On a une arborescence de challenge hardware avec plusieurs fichiers VHDL (langage de description matériel) :
text

backdoor.vhdl
encryption.vhdl
key.vhdl
tpm.vhdl
schematic.png

Le service distant écoute sur 154.57.164.78:44947 et demande un signal binaire de 16 bits.
🔍 Analyse

On commence par inspecter les fichiers VHDL, qui décrivent le fonctionnement logique d'un TPM (Trusted Platform Module) — logique puisqu'on parle de sécurité matérielle.

En lisant backdoor.vhdl :
vhdl

entity backdoor is
	Port (
		D : in STD_LOGIC_VECTOR(15 downto 0);
		B : out STD_LOGIC
	);
end backdoor;

architecture Behavioral of backdoor is
    constant pattern : STD_LOGIC_VECTOR(15 downto 0) := "1111111111101001";
begin
	process(D)
	begin
        if D = pattern then
            B <= '1';
        else
            B <= '0';
        end if;
	end process;
end Behavioral;
 Ce que fait ce module :

    Il prend une entrée D de 16 bits

    Il compare D à un pattern hardcodé : "1111111111101001"

    Si D == pattern, la sortie B passe à 1 → la backdoor est activée

Autrement dit, une porte dérobée est cachée dans le design : si on fournit exactement la valeur 0xFFE9 (0b1111111111101001), on déclenche le signal de backdoor qui permet de bypasser la logique normale.
 Exploitation

On se connecte au service :
bash

nc 154.57.164.78 44947

Le service demande un signal binaire de 16 bits. On envoie simplement le pattern trouvé dans le fichier VHDL :
text

Input : 1111111111101001
Output: 0110001111100001

Et le serveur répond :
text

You triggered the backdoor here is the flag: HTB{REDACTED}

🏁 Flag
text

HTB{REDACTED}

 Leçon retenue

En reverse hardware, il faut toujours lire tous les fichiers HDL fournis : les backdoors sont souvent cachées sous forme de comparaisons de constantes (pattern) ou d'états particuliers. Un simple grep pattern sur les fichiers VHDL aurait suffi. Le nom du challenge ("It's oops PM" → jeu de mot sur TPM) confirme qu'il s'agit d'un TPM compromis par une porte dérobée.

"""PC D: consome sub-d-gases e sub-d-eventos no mesmo processo (dois streaming pulls).

As duas assinaturas gravam no mesmo pc-d.csv (coluna "assinatura" separa). O idle-timeout
conta a partir da ultima mensagem de qualquer uma das duas.

Uso: python src/consumer_pc_d.py --run-id <id> [--cenario teste] [--rep 1] [--idle-timeout 15]
"""

from common import rodar_consumidor

if __name__ == "__main__":
    rodar_consumidor("pc-d")

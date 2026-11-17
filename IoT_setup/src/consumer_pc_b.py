"""PC B: consome sub-b-ambiente (topico ambiente).

Uso: python src/consumer_pc_b.py --run-id <id> [--cenario teste] [--rep 1] [--idle-timeout 15]
"""

from common import rodar_consumidor

if __name__ == "__main__":
    rodar_consumidor("pc-b")

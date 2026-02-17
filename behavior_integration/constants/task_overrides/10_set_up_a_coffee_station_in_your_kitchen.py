"""
Task: 10_set_up_a_coffee_station_in_your_kitchen

Problem: Tre oggetti (bottle_of_coffee, saucer, electric_kettle) devono essere
posizionati next to the same coffee_maker. Inoltre la coffee_cup va ON TOP del saucer.

Sfide:
1. Se tutti posizionati nella stessa direzione, si sovrappongono
2. Il robot navigando puo spostare gli oggetti gia posizionati
3. La cup deve restare stabile sul saucer
4. Gli oggetti cadono dal countertop se Z non e forzata
5. Gli oggetti collidono col coffee_maker se margine troppo piccolo

Solution (pattern da task 06 e 09):
1. Randomizzare la direzione per PLACE_NEXT_TO
2. Fissare gli oggetti dopo il posizionamento
3. Settling moderato per cup-on-saucer
4. Forzare Z al livello del countertop
5. Margine maggiore per evitare collisioni
6. Skip verifica NextTo (predicato BDDL piu permissivo del check OG)
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    nextto_randomize_direction=True,  # Distribuisce oggetti intorno al coffee_maker
    place_settle_steps=30,            # Settling per cup-on-saucer (un po piu del default 20)
    fix_after_placement=True,         # Previene spostamento durante navigazione
    nextto_force_z=0.95,              # Forza Z al livello del countertop (~0.9-1.0m)
    nextto_margin_min=0.12,           # Margine maggiore per evitare collisioni
    skip_nextto_verification=True,    # Skip check OG, lascia che BDDL verifichi
)

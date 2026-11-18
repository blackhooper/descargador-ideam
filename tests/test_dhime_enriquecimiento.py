import pandas as pd
from modules import dhime_enriquecimiento as d

PROG = [{"DESCRIPCION": "NV niveles", "TIPO": "Hidrológico", "IDESTACION": 22067020},
        {"DESCRIPCION": "QL caudales", "TIPO": "Hidrológico", "IDESTACION": 22067020},
        {"DESCRIPCION": "mant generales ano", "TIPO": "Mantenimiento", "IDESTACION": 22067020},
        {"DESCRIPCION": "pinturas estacion ano", "TIPO": "Mantenimiento", "IDESTACION": 1}]
SUB = {"Data": [{"Nombre": "Alt", "Estaciones": [{"IdEstacion": 22067020}, {"IdEstacion": 27015330, "Nombre": "Y [27015330]"}]}]}
HOM = {"Data": [{"IdEstacionOrigen": 27015330, "IdEstacionDestino": 27015070},
                {"IdEstacionOrigen": 27015070, "IdEstacionDestino": 27015999}]}


def test_enriquecer():
    tablas = {"programas": d.procesar_programas(PROG), "subredes": d.procesar_subredes(SUB),
              "homologacion": d.procesar_homologacion(HOM)}
    cat = d.enriquecer_catalogo(pd.DataFrame({"idestacion": ["22067020", "27015330", "1"]}), tablas)
    assert cat.loc[0, "programas"] == "Caudal; Nivel"
    assert cat.loc[1, "subredes"] == "Alt"
    assert cat.loc[1, "grupo_homologacion"] == "27015070" and cat.loc[1, "homologa_con"] == "27015070, 27015999"
    assert cat.loc[2, "programas"] == ""   # solo tenia mantenimiento
    assert len(d.mide(cat, "CAUDAL")) == 1

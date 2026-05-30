"""
Phase 7 seed data — European imaging facilities.

Source: publicly available information from Euro-BioImaging node listings
(eurobioimaging.eu), institution websites, and ELIXIR node pages.
All data derived from public sources only.
"""

INITIATIVES: list[dict] = [
    {
        "id": "euro_bioimaging",
        "name": "Euro-BioImaging",
        "scope": "pan-European",
        "homepage": "https://www.eurobioimaging.eu",
    },
    {
        "id": "elixir",
        "name": "ELIXIR",
        "scope": "pan-European",
        "homepage": "https://elixir-europe.org",
    },
    {
        "id": "esfri",
        "name": "ESFRI",
        "scope": "pan-European",
        "homepage": "https://www.esfri.eu",
    },
]

INSTITUTIONS: list[dict] = [
    {"id": "scilifelab",    "name": "SciLifeLab",                         "country": "SE", "homepage": "https://www.scilifelab.se"},
    {"id": "embl",          "name": "EMBL Heidelberg",                    "country": "DE", "homepage": "https://www.embl.org"},
    {"id": "karolinska",    "name": "Karolinska Institutet",              "country": "SE", "homepage": "https://ki.se"},
    {"id": "dkfz",          "name": "DKFZ",                               "country": "DE", "homepage": "https://www.dkfz.de"},
    {"id": "institut_curie","name": "Institut Curie",                     "country": "FR", "homepage": "https://science.institut-curie.org"},
    {"id": "ku_leuven",     "name": "KU Leuven",                          "country": "BE", "homepage": "https://www.kuleuven.be"},
    {"id": "univ_helsinki", "name": "University of Helsinki",             "country": "FI", "homepage": "https://www.helsinki.fi"},
    {"id": "univ_oslo",     "name": "University of Oslo",                 "country": "NO", "homepage": "https://www.uio.no"},
    {"id": "dtu",           "name": "DTU Biosustain",                     "country": "DK", "homepage": "https://www.biosustain.dtu.dk"},
    {"id": "img_prague",    "name": "Institute of Molecular Genetics CAS","country": "CZ", "homepage": "https://www.img.cas.cz"},
]

TECHNIQUES: list[dict] = [
    {"id": "light_microscopy",       "name": "Light microscopy",                            "edam_topic": "topic_3382"},
    {"id": "confocal",               "name": "Confocal microscopy",                         "edam_topic": "topic_3382"},
    {"id": "electron_microscopy",    "name": "Electron microscopy",                         "edam_topic": "topic_0611"},
    {"id": "cryo_em",                "name": "Cryo-EM",                                     "edam_topic": "topic_1317"},
    {"id": "correlative_microscopy", "name": "Correlative light and electron microscopy",   "edam_topic": "topic_3383"},
    {"id": "image_analysis",         "name": "Image analysis",                              "edam_topic": "topic_3372"},
    {"id": "biomedical_imaging",     "name": "Biomedical imaging",                          "edam_topic": "topic_3384"},
    {"id": "flow_cytometry",         "name": "Flow cytometry",                              "edam_topic": "topic_2229"},
    {"id": "expansion_microscopy",   "name": "Expansion microscopy",                        "edam_topic": "topic_3382"},
]

FACILITIES: list[dict] = [
    {
        "id": "scilifelab_bioimaging",
        "name": "SciLifeLab BioImage Informatics",
        "city": "Uppsala",
        "institution": "scilifelab",
        "initiatives": ["euro_bioimaging", "elixir"],
        "accessType": "REMOTE",
        "techniques": ["image_analysis", "light_microscopy"],
    },
    {
        "id": "scilifelab_lci",
        "name": "SciLifeLab Live Cell Imaging",
        "city": "Stockholm",
        "institution": "scilifelab",
        "initiatives": ["euro_bioimaging"],
        "accessType": "PHYSICAL",
        "techniques": ["light_microscopy", "confocal"],
    },
    {
        "id": "embl_almf",
        "name": "EMBL Advanced Light Microscopy Facility",
        "city": "Heidelberg",
        "institution": "embl",
        "initiatives": ["euro_bioimaging"],
        "accessType": "BOTH",
        "techniques": ["light_microscopy", "confocal", "expansion_microscopy"],
    },
    {
        "id": "embl_cryoem",
        "name": "EMBL Cryo-EM Facility",
        "city": "Heidelberg",
        "institution": "embl",
        "initiatives": ["euro_bioimaging"],
        "accessType": "PHYSICAL",
        "techniques": ["cryo_em", "electron_microscopy"],
    },
    {
        "id": "ki_lci",
        "name": "Karolinska Live Cell Imaging",
        "city": "Stockholm",
        "institution": "karolinska",
        "initiatives": ["euro_bioimaging"],
        "accessType": "PHYSICAL",
        "techniques": ["light_microscopy", "confocal", "flow_cytometry"],
    },
    {
        "id": "dkfz_microscopy",
        "name": "DKFZ Light Microscopy Facility",
        "city": "Heidelberg",
        "institution": "dkfz",
        "initiatives": ["euro_bioimaging"],
        "accessType": "PHYSICAL",
        "techniques": ["light_microscopy", "confocal", "image_analysis"],
    },
    {
        "id": "curie_imaging",
        "name": "Institut Curie Cell and Tissue Imaging",
        "city": "Paris",
        "institution": "institut_curie",
        "initiatives": ["euro_bioimaging"],
        "accessType": "BOTH",
        "techniques": ["light_microscopy", "correlative_microscopy", "image_analysis"],
    },
    {
        "id": "vib_bioimaging",
        "name": "VIB Bioimaging Core",
        "city": "Leuven",
        "institution": "ku_leuven",
        "initiatives": ["euro_bioimaging"],
        "accessType": "PHYSICAL",
        "techniques": ["light_microscopy", "confocal", "electron_microscopy"],
    },
    {
        "id": "helsinki_bioimaging",
        "name": "University of Helsinki Bioimaging",
        "city": "Helsinki",
        "institution": "univ_helsinki",
        "initiatives": ["euro_bioimaging", "elixir"],
        "accessType": "PHYSICAL",
        "techniques": ["light_microscopy", "correlative_microscopy", "flow_cytometry"],
    },
    {
        "id": "normic_oslo",
        "name": "NorMIC Oslo",
        "city": "Oslo",
        "institution": "univ_oslo",
        "initiatives": ["euro_bioimaging"],
        "accessType": "PHYSICAL",
        "techniques": ["light_microscopy", "confocal", "image_analysis"],
    },
    {
        "id": "danish_bioimaging",
        "name": "Danish BioImaging",
        "city": "Copenhagen",
        "institution": "dtu",
        "initiatives": ["euro_bioimaging"],
        "accessType": "BOTH",
        "techniques": ["light_microscopy", "biomedical_imaging", "image_analysis"],
    },
    {
        "id": "czech_bioimaging",
        "name": "Czech-BioImaging",
        "city": "Vestec",
        "institution": "img_prague",
        "initiatives": ["euro_bioimaging"],
        "accessType": "PHYSICAL",
        "techniques": ["light_microscopy", "electron_microscopy", "correlative_microscopy"],
    },
]

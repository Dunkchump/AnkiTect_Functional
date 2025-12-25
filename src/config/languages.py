"""Language-specific configurations."""

LANG_CONFIG = {
    "DE": {
        "deck_name": "DE Das Fundament",
        "voice": "de-DE-ConradNeural",
        "voice_id": "CONRAD",
        "label": "DEUTSCH",
        "strip_regex": r'^(der|die|das)\s+',
        "forvo_lang": "de",
        "model_id": 1607393148,
        "available_voices": [
            "de-DE-ConradNeural",
            "de-DE-AmalaNeural",
            "de-DE-KatjaNeural",
            "de-DE-KillianNeural",
        ],
        "month_names": {
            1: "Januar", 2: "Februar", 3: "März", 4: "April",
            5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
            9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
        }
    },
    "EN": {
        "deck_name": "GB The Cornerstone",
        "voice": "en-GB-SoniaNeural",
        "voice_id": "SONIA",
        "label": "ENGLISH",
        "strip_regex": r'^(to|the|a|an)\s+',
        "forvo_lang": "en",
        "model_id": 1607393149,
        "available_voices": [
            "en-GB-SoniaNeural",
            "en-GB-RyanNeural",
            "en-GB-ThomasNeural",
            "en-GB-LibbyNeural",
        ],
        "month_names": {
            1: "January", 2: "February", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December"
        }
    }
}

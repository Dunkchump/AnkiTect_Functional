"""Card templates with CSS and HTML."""


class CardTemplates:
    """Container for all card templates and styling."""
    
    CSS = """
    .card { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #333; background-color: #f4f6f9; margin: 0; padding: 0; }
    .card-container { background: #fff; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); overflow: hidden; max-width: 500px; margin: 10px auto; text-align: left; padding-bottom: 15px; position: relative; }
    
    .header-box { padding: 25px 20px; text-align: center; color: white !important; font-weight: bold; background-color: #34495e; }
    .bg-der { background: linear-gradient(135deg, #2980b9, #3498db); } 
    .bg-die { background: linear-gradient(135deg, #c0392b, #e74c3c); } 
    .bg-das { background: linear-gradient(135deg, #27ae60, #2ecc71); } 
    .bg-none { background: linear-gradient(135deg, #8e44ad, #9b59b6); } /* Фиолетовый для немецких слов без артиклей */
    .bg-en, .bg-noun { background: linear-gradient(135deg, #2c3e50, #4ca1af); }
    
    .word-main { font-size: 2.5em; font-weight: 800; margin: 0; letter-spacing: -0.5px; line-height: 1.1; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }
    .word-meta { font-size: 0.9em; opacity: 0.9; margin-top: 8px; font-family: monospace; }
    
    .section { padding: 12px 20px; border-bottom: 1px solid #f2f2f2; }
    .label { font-size: 0.7em; text-transform: uppercase; color: #adb5bd; font-weight: 800; letter-spacing: 1.2px; display: block; margin-bottom: 6px; }
    .definition { font-size: 1.1em; font-weight: 600; color: #212529; }
    
    .morph-pill { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 0.8em; background: #e9ecef; color: #495057; font-weight: bold; margin-right: 5px; }
    .section .morph-pill.bg-en { display: none; }
    
    /* NUANCE (Clean Grey) */
    .nuance-sub {
        font-size: 0.95em;
        color: #666;
        margin-bottom: 12px;
        line-height: 1.4;
        font-weight: 500;
    }

    /* ETYMOLOGY (Yellow Box) */
    .narrative {
        font-style: italic; color: #555; background: #fff9db; 
        padding: 12px; border-radius: 8px; font-size: 0.95em;
        margin-top: 10px; border-left: 4px solid #f1c40f; line-height: 1.5;
    }

    /* MEMORY HOOK & HINT (Blue Box) */
    .mnemonic-box {
        background-color: #e7f5ff; /* Light Blue Background */
        color: #1971c2;            /* Dark Blue Text */
        padding: 12px;
        border-radius: 8px;
        font-size: 0.95em;
        border-left: 4px solid #1971c2;
    }

    /* ANALOGUES TABLE (BULLETPROOF) */
    .analogues-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.95em;
        margin-top: 5px;
    }
    .ana-row td {
        padding-bottom: 6px; /* Spacing between rows */
        vertical-align: top;
    }
    .ana-lang {
        text-align: right;
        font-weight: bold;
        color: #adb5bd;
        padding-right: 12px;
        border-right: 2px solid #e9ecef; /* The line */
        width: 35px; /* Fixed width prevents jumping */
        white-space: nowrap;
    }
    .ana-word {
        text-align: left;
        padding-left: 12px;
        color: #343a40;
    }

    .sentence-container {
        display: flex; justify-content: space-between; align-items: center;
        background-color: #f8f9fa; border-radius: 6px;
        padding: 6px 10px; margin-bottom: 6px; border-left: 3px solid #dee2e6;
    }
    .sentence-text { flex-grow: 1; margin-right: 10px; font-size: 0.9em; line-height: 1.35; color: #343a40; }
    
    .replay-btn {
        background: white; color: #495057; border: 1px solid #ced4da; 
        border-radius: 50%; width: 26px; height: 26px;
        font-size: 12px; cursor: pointer; flex-shrink: 0; display: flex; align-items: center; justify-content: center;
        transition: all 0.2s; box-shadow: 0 1px 2px rgba(0,0,0,0.05); user-select: none;
    }
    .replay-btn:active { background: #e9ecef; transform: scale(0.95); }
    
    .img-box { width: 100%; margin-top: 5px; border-radius: 8px; overflow: hidden; display: flex; justify-content: center; background: #000; }
    .img-box img { width: 100%; height: auto; object-fit: cover; display: block; }

    .footer-controls { 
        display: flex; justify-content: center; align-items: center; 
        gap: 15px; padding: 15px 20px; background: #f8f9fa; border-top: 1px solid #eee; 
    }
    
    .pill-btn {
        display: inline-flex; justify-content: center; align-items: center;
        width: 120px; height: 36px; box-sizing: border-box;
        text-decoration: none; background: white; border: 1px solid #ced4da; 
        color: #495057; border-radius: 20px; font-size: 0.85em; font-weight: 600; 
        cursor: pointer; transition: background 0.2s; padding: 0; margin: 0; font-family: inherit;
    }
    .pill-btn:hover { background: #f1f3f5; }
    .pill-btn:active { transform: translateY(1px); }

    .tags-footer { text-align: center; padding: 10px; font-size: 0.75em; color: #ced4da; }
    .tag-pill { display: inline-block; background: #f1f3f5; padding: 2px 8px; border-radius: 10px; margin: 0 2px; }
    
    .hidden-native-audio { display: none; }
    """

    FRONT_REC = """<div class="card-container"><div style="padding:50px 20px; text-align:center;"><div style="font-size:0.85em; color:#bbb; text-transform:uppercase;">__LABEL__</div><div style="font-size:3em; font-weight:800; color:#2c3e50; margin-top:15px;">{{TargetWord}}</div><div style="color:#95a5a6; margin-top:10px; font-family:monospace;">{{Part_of_Speech}}</div></div></div>"""
    
    JS_PLAYER = """
    <script>
    function toggleAudio(audioId, btn) {
        var audio = document.getElementById(audioId);
        if (!audio) return;
        if (!audio.paused) {
            audio.pause();
            btn.innerHTML = "▶";
        } else {
            document.querySelectorAll('audio').forEach(el => { el.pause(); el.currentTime = 0; });
            document.querySelectorAll('.replay-btn').forEach(b => b.innerHTML = "▶");
            audio.play();
            btn.innerHTML = "⏸";
        }
        audio.onended = function() { btn.innerHTML = "▶"; };
    }
    function playMainAudio() { var a = document.getElementById('main_word_audio'); if(a){a.currentTime=0; a.play();} }

    try {
        var count = 200;
        var defaults = { origin: { y: 0.7 } };
        function fire(particleRatio, opts) {
          confetti(Object.assign({}, defaults, opts, { particleCount: Math.floor(count * particleRatio) }));
        }
        setTimeout(function() {
            fire(0.25, { spread: 26, startVelocity: 55, });
            fire(0.2, { spread: 60, });
        }, 300);
    } catch (e) { console.log("Confetti err"); }
    </script>
    <script src="_confetti.js"></script>
    """

    BACK_REC = """
    <div class="card-container">
        <div class="header-box bg-{{Gender}}">
            <div class="word-main">{{TargetWord}}</div>
            <div class="word-meta">/{{IPA}}/ • {{Part_of_Speech}}</div>
        </div>
        
        <div class="section"><span class="label">MEANING</span><div class="definition">{{Meaning}}</div></div>
        
        <div class="section">
            <span class="label">MORPHOLOGY & ETYMOLOGY</span>
            <div style="margin-bottom:10px;">
                <span class="morph-pill bg-{{Gender}}" style="color:white;">{{Gender}}</span>
                {{#Morphology}}<span class="morph-pill">{{Morphology}}</span>{{/Morphology}}
            </div>
            {{#Etymology}}<div class="narrative">{{Etymology}}</div>{{/Etymology}}
        </div>

        <div class="section">
            <span class="label">CONTEXT</span>
            {{#Nuance}}<div class="nuance-sub">{{Nuance}}</div>{{/Nuance}}
            
            {{#Sentence_1}}
            <div class="sentence-container">
                <span class="sentence-text">{{Sentence_1}}</span>
                <button class="replay-btn" onclick="toggleAudio('audio_s1', this)">▶</button>
            </div>
            <audio id="audio_s1" src="{{Audio_Sent_1}}" preload="none"></audio>
            {{/Sentence_1}}

            {{#Sentence_2}}
            <div class="sentence-container">
                <span class="sentence-text">{{Sentence_2}}</span>
                <button class="replay-btn" onclick="toggleAudio('audio_s2', this)">▶</button>
            </div>
            <audio id="audio_s2" src="{{Audio_Sent_2}}" preload="none"></audio>
            {{/Sentence_2}}

            {{#Sentence_3}}
            <div class="sentence-container">
                <span class="sentence-text">{{Sentence_3}}</span>
                <button class="replay-btn" onclick="toggleAudio('audio_s3', this)">▶</button>
            </div>
            <audio id="audio_s3" src="{{Audio_Sent_3}}" preload="none"></audio>
            {{/Sentence_3}}
            
            <div style="font-size:0.8em; color:#aaa; font-style:italic; margin-top:15px; opacity: 0.8; line-height: 1.4;">
                {{ContextTranslation}}
            </div>
        </div>

        <div class="section"><span class="label">MEMORY HOOK</span><div class="mnemonic-box">💡 {{Mnemonic}}</div></div>

        {{#Analogues}}
        <div class="section">
            <span class="label">ANALOGUES</span>
            {{Analogues}}
        </div>
        {{/Analogues}}
        
        {{#Image}}<div class="section" style="padding:0;"><div class="img-box">{{Image}}</div></div>{{/Image}}
        
        <div class="footer-controls">
            <a class="pill-btn" href="https://forvo.com/word/{{TargetWord}}/#__FORVO__">🔊 Forvo</a>
            <button class="pill-btn" onclick="playMainAudio()">🎧 Listen</button>
        </div>
        
        <div class="tags-footer">{{#Tags}}<span class="tag-pill">{{Tags}}</span>{{/Tags}}</div>

        <div class="hidden-native-audio">{{AudioWord}}</div>
        <audio id="main_word_audio" src="{{Audio_Path_Word}}" preload="auto"></audio>
    </div>
    """ + JS_PLAYER
    
    # Blue Hint Box in Production Card
    FRONT_PROD = """<div class="card-container"><div style="padding:40px 20px; text-align:center;"><div style="font-size:0.8em; color:#bbb; text-transform:uppercase;">TRANSLATE</div><div style="font-size:1.8em; font-weight:bold; color:#2c3e50; margin-top:10px;">{{Meaning}}</div><div class="mnemonic-box" style="margin-top:20px;border-left: none">Hint: {{Mnemonic}}</div></div></div>"""
    FRONT_LIST = """<div class="card-container"><div style="padding:50px 20px; text-align:center;"><div style="font-size:4em;">🎧</div><div style="margin-top:20px; color:#888;">Listen & Recognize</div><div style="display:none;">{{AudioWord}}</div><button class="pill-btn" style="margin-top:20px; width:150px;" onclick="document.getElementById('q_audio').play()">▶ Play</button><audio id="q_audio" src="{{Audio_Path_Word}}"></audio></div></div>"""
    FRONT_CLOZE = r"""<div class="card-container"><div class="header-box bg-none"><div style="font-size:1.2em;">Complete the Context</div></div><div class="section" style="padding: 20px;"><div id="context-sentence" style="font-size:1.1em; line-height:1.6;">{{ContextSentences}}</div></div></div><script>var contextDiv=document.getElementById("context-sentence");if(contextDiv){var content=contextDiv.innerHTML;var re=/<b>(.*?)<\/b>/gi;contextDiv.innerHTML=content.replace(re,"<span style='color:#3498db; border-bottom:2px solid #3498db; font-weight:bold;'>[...]</span>");}</script>"""
    
    @classmethod
    def get_recognition_template(cls, label: str):
        """Get recognition card with label substitution."""
        return cls.FRONT_REC.replace("__LABEL__", label)
    
    @classmethod
    def get_back_template(cls, forvo_code: str):
        """Get back card with Forvo code substitution."""
        return cls.BACK_REC.replace("__FORVO__", forvo_code)

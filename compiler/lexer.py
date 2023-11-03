import ply.lex as lex


class MyLexer(object):
    literals = [
        "[",
        "]",
        "{",
        "}",
        "(",
        ")",
        ":",
        ";",
        "=",
        ",",
        ">",
        "-",
        "|",
        "."
    ]

    # Declare the state
    states = (("CCODE", "exclusive"),)

    # Match the ##. Enter ccode state.
    def t_BEGIN_CCODE(self, t):
        r"\$\$"
        assert t.lexer.current_state() == "INITIAL"
        t.lexer.push_state("CCODE")  # Enter 'ccode' state
        self.parenstack = (-100, None)
        self.bracestack = (-100, None)
        self.parenlevel = 0
        self.bracelevel = 0
        return t

    def t_CCODE_end(self, t):
        r"\$\$"
        assert t.lexer.current_state() == "CCODE"
        t.lexer.pop_state()  # Enter INITIAL state
        assert t.lexer.current_state() == "INITIAL"
        t.type="CCODE_end"
        return t

    def t_CCODE_escape(self, t):
        r"\\[.\n]"
        t.type="CCODE_TOKEN"
        t.lexer.lineno += t.value.count("\n")
        return t

    def t_CCODE_string(self, t):
        r'\"([^\\\n]|(\\.))*?\"'
        t.type="CCODE_TOKEN"
        t.lexer.lineno += t.value.count("\n")
        return t

    def t_CCODE_comment(self, t):
        r'(/\*(.|\n)*?\*/)|(//.*)'
        t.type="CCODE_TOKEN"
        t.lexer.lineno += t.value.count("\n")
        return t

    def t_CCODE_oparen(self, t):
        r'\('
        t.type="CCODE_OPAREN"
        self.parenlevel+=1
        return t

    def t_CCODE_cparen(self, t):
        r'\)'
        t.type="CCODE_CPAREN"
        self.parenlevel-=1
        return t

    def t_CCODE_obrace(self, t):
        r'\{'
        t.type="CCODE_OBRACE"
        self.bracelevel+=1
        return t

    def t_CCODE_cbrace(self, t):
        r'\}'
        t.type="CCODE_CBRACE"
        self.bracelevel-=1
        return t

    def t_CCODE_semicolon(self, t):
        r';'
        (plevel, prest) = self.parenstack
        if(self.parenlevel==plevel):
            self.parenstack=prest
            t.type="CCODE_SEMICOLON"
        else:
            t.type="CCODE_TOKEN"
        return t
    
    def t_CCODE_comma(self, t):
        r','
        (plevel, prest) = self.parenstack
        if(self.parenlevel==plevel+1):
            t.type="CCODE_COMMA"
        else:
            t.type="CCODE_TOKEN"
        return t

    def t_CCODE_rest(self, t):
        r'[^/\\{}()\$;,\"]+'
        t.type="CCODE_TOKEN"
        t.lexer.lineno += t.value.count("\n")
        return t
    
    def t_CCODE_escape_yield(self, t):
        r'\$yield[\t ]+(?P<evid>[a-zA-Z_][a-zA-Z_0-9]*)[\t ]*\('
        self.parenstack = (self.parenlevel, self.parenstack)
        self.parenlevel+=1
        t.type="CCODE_YIELD"
        t.value=t.lexer.lexmatch.group("evid")
        return t
    
    def t_CCODE_escape_switchto(self, t):
        r'\$switch[\t ]+to[\t ]+(?P<rsid>[a-zA-Z_][a-zA-Z_0-9]*)[\t ];'
        t.type="CCODE_SWITCHTO"
        t.value=t.lexer.lexmatch.group("rsid")
        return t
    
    def t_CCODE_escape_continue(self, t):
        r'\$continue;'
        t.type="CCODE_CONTINUE"
        return t
    
    def t_CCODE_escape_drop(self, t):
        r'\$drop[\t ]+(?P<amnt>[1-9][0-9]*)[\t ]+from[\t ]+(?P<esid1>[a-zA-Z_][a-zA-Z_0-9]*)[\t ]*(\[[\t ]*(?P<idx1>(([1-9][0-9]*)|([a-zA-Z_][a-zA-Z0-9_]*)))[\t ]*\])?[\t ]*;'
        t.type="CCODE_DROP"
        idx=t.lexer.lexmatch.group("idx1")
        if(idx==None):
            idx="0"
        t.value=(t.lexer.lexmatch.group("amnt"), t.lexer.lexmatch.group("esid1"), idx)
        return t
    
    def t_CCODE_escape_remove(self, t):
        r'\$remove[\t ]+(?P<esid2>[a-zA-Z_][a-zA-Z_0-9]*)[\t ]*(\[[\t ]*(?P<idx2>(([1-9][0-9]*)|([a-zA-Z_][a-zA-Z0-9_]*)))[\t ]*\])?[\t ]+from[\t ]+(?P<bgid1>[a-zA-Z_][a-zA-Z0-9_]*)[\t ]*;'
        t.type="CCODE_REMOVE"
        idx=t.lexer.lexmatch.group("idx2")
        if(idx==None):
            idx="0"
        t.value=(t.lexer.lexmatch.group("esid2"), idx, t.lexer.lexmatch.group("bgid1"))
        return t
    
    def t_CCODE_escape_add(self, t):
        r'\$add[\t ]+(?P<esid3>[a-zA-Z_][a-zA-Z_0-9]*)[\t ]*(\[[\t ]*(?P<idx3>(([1-9][0-9]*)|([a-zA-Z_][a-zA-Z0-9_]*)))[\t ]*\])?[\t ]+to[\t ]+(?P<bgid2>[a-zA-Z_][a-zA-Z0-9_]*)[\t ]*;'
        t.type="CCODE_ADD"
        idx=t.lexer.lexmatch.group("idx3")
        if(idx==None):
            idx="0"
        t.value=(t.lexer.lexmatch.group("esid3"), idx, t.lexer.lexmatch.group("bgid2"))
        return t
    
    def t_CCODE_escape_field(self, t):
        r'\$(?P<esid4>[a-zA-Z_][a-zA-Z_0-9]*)(\[[\t ]*(?P<idx4>(([1-9][0-9]*)|([a-zA-Z_][a-zA-Z0-9_]*)))[\t ]*\])?\.(?P<fname>[a-zA-Z_][a-zA-Z0-9_]*);'
        t.type="CCODE_FIELD"
        idx=t.lexer.lexmatch.group("idx4")
        if(idx==None):
            idx="0"
        t.value=(t.lexer.lexmatch.group("esid4"), idx, t.lexer.lexmatch.group("fname"))
        return t

    # def t_CCODE_STATEMENT_INITIAL(self, t):
    #     r"\$"
    #     assert t.lexer.current_state() == "CCODE"
    #     t.lexer.push_state("INITIAL")  # Enter 'initial' state

    # def t_CCODE_TOKEN(self, t):
    #     r"[^$]+"
    #     assert t.lexer.current_state() == "CCODE"
    #     t.type = "CCODE_TOKEN"
    #     return t

    # Ignored characters (whitespace)
    # t_CCODE_ignore = " \t\n"

    # For bad characters, we just skip over it
    def t_CCODE_error(self, t):
        t.lexer.skip(1)
        print("error")

    def t_semicol(self, t):
        r";"
        t.type = ";"

        if len(t.lexer.lexstatestack) > 1:
            assert t.lexer.current_state() == "INITIAL"
            # end code statement
            t.lexer.pop_state()
            assert t.lexer.current_state() == "CCODE"
        return t

    def t_2dots(self, t):
        r"^:$"
        t.type = ":"
        return t

    def t_comma(self, t):
        r"^,$"
        t.type = ","
        return t

    def t_doubleq(self, t):
        r"=="
        t.type="DOUBLEEQ"
        return t 
    def t_geq(self, t):
        r"\>="
        t.type="GEQ"
        return t 
    def t_leq(self, t):
        r"\<="
        t.type="LEQ"
        return t  
    def t_gt(self, t):
        r"\>"
        t.type="GT"
        return t 
    def t_lt(self, t):
        r"\<"
        t.type="LT"
        return t
    def t_and(self, t):
        r"\&\&"
        t.type="AND"
        return t 
    def t_or(self, t):
        r"\|\|"
        t.type="OR"
        return t  

    def t_band(self, t):
        r"\&"
        t.type = "BAND"
        return t
    def t_not(self, t):
        r"\!"
        t.type = "NOT"
        return t

    def t_equal(self, t):
        r"="
        t.type = "="
        return t

    def t_lcurly(self, t):
        r"\{"
        t.type = "{"  # Set token type to the expected literal
        return t

    def t_rcurly(self, t):
        r"\}"
        t.type = "}"  # Set token type to the expected literal
        return t

    def t_lbracket(self, t):
        r"\["
        t.type = "["  # Set token type to the expected literal
        return t

    def t_rbracket(self, t):
        r"\]"
        t.type = "]"  # Set token type to the expected literal
        return t

    def t_lparenthesis(self, t):
        r"\("
        t.type = "("  # Set token type to the expected literal
        return t

    def t_rparenthesis(self, t):
        r"\)"
        t.type = ")"  # Set token type to the expected literal
        return t

    def t_pipe(self, t):
        r"\|"
        t.type = "|"  # Set token type to the expected literal
        return t
    
    def t_arrow(self, t):
        r"\->"
        t.type="ARROW"
        return t
    
    def t_times(self, t):
        r"\*"
        t.type="TIMES"
        return t
    
    def t_plus(self, t):
        r"\+"
        t.type="PLUS"
        return t
    
    def t_minus(self, t):
        r"\-"
        t.type="MINUS"
        return t

    reserved = {
        "_" : "_",
        "if": "IF",
        "then": "THEN",
        "else": "ELSE",
        "stream": "STREAM",
        "type": "TYPE",
        "autodrop": "AUTODROP",
        "infinite": "INFINITE",
        "blocking": "BLOCKING",
        "drop": "DROP",
        "forward": "FORWARD",
        "on": "ON",
        "done": "DONE",
        "nothing": "NOTHING",
        "to": "TO",
        "where": "WHERE",
        "rule": "RULE",
        "set": "SET",
        "arbiter": "ARBITER",
        "monitor": "MONITOR",
        "event": "EVENT",
        "source": "SOURCE",
        "from": "FROM",
        "round": "ROUND",
        "robin": "ROBIN",
        "extends": "EXTENDS",
        "creates": "CREATES",
        "at": "AT",
        "most": "MOST",
        "process": "PROCESS",
        "using": "USING",
        "dynamic": "DYNAMIC",
        "buffer": "BUFFER",
        "group": "GROUP",
        "match": "MATCH",
        "fun": "FUN",
        "choose": "CHOOSE",
        "by": "BY",
        "hole" : "HOLE",
        "globals": "GLOBALS",
        "startup": "STARTUP",
        "cleanup": "CLEANUP",
        "loopdebug": "LOOPDEBUG",
        "processor": "PROCESSOR",
        "include": "INCLUDE",
        "includes": "INCLUDES",
        "aggregate": "AGGREGATE",
        "order": "ORDER",
        "all": "ALL",
        "in": "IN",
        "first" : "FIRST",
        "last" : "LAST",
        "COUNT": "COUNT",
        "MAX": "MAX",
        "MIN": "MIN",
        "always": "ALWAYS",
        "\+": "PLUS",
        "\*": "TIMES",
        "\-": "MINUS",
        "wait": "WAIT",
        "ignore": "IGNORE",
        "assume": "ASSUME",
        "shared": "SHARED",
        "\->" : "ARROW"
    }

    # Token names.
    tokens = [
        # data types
        "BOOL",
        "INT",
        "ID",
        # operators
        "DOUBLEQ",
        "GEQ",
        "LEQ",
        "LT",
        "GT",
        "AND",
        "OR",
        "BAND",
        "NOT",
        # ccode
        "CCODE_TOKEN",  # matches everything except $
        "BEGIN_CCODE",
        "CCODE_end",
        "CCODE_YIELD",
        "CCODE_FIELD",
        "CCODE_OPAREN",
        "CCODE_CPAREN",
        "CCODE_OBRACE",
        "CCODE_CBRACE",
        "CCODE_SEMICOLON",
        "CCODE_COMMA",
        "CCODE_DROP",
        "CCODE_REMOVE",
        "CCODE_ADD",
        "CCODE_CONTINUE",
        "CCODE_SWITCHTO"
    ] + list(reserved.values())

    # Regular expression rules for simple tokens

    # A regular expression rule with some action code
    # Note addition of self parameter since we're in a class
    def t_INT(self, t):
        r"((\-?|\+?)([1-9][0-9]*)|0)"
        t.value = int(t.value)
        return t
    
    def t_BOOL(self, t):
        r"(true)|(false)"
        return t

    def t_ID(self, t):
        r"[a-zA-Z_][a-zA-Z_0-9]*"
        # for variable names and keywords
        t.type = self.reserved.get(t.value, "ID")  # Check for reserved words
        return t

    # Define a rule so we can track line numbers
    def t_newline(self, t):
        r"\n+"
        t.lexer.lineno += len(t.value)

    # A string containing ignored characters (spaces and tabs)
    t_ignore = " \t"
    t_CCODE_ignore = ""

    # Error handling rule
    def t_error(self, t):
        print(
            f"Illegal character {t.value[0]} (line {t.lexer.lineno}) (pos {t.lexer.lexpos})"
        )
        t.lexer.skip(1)

    def reset(self):
        self.lexer.lineno=1
        self.parenstack = (-100, None)
        self.bracestack = (-100, None)
        self.parenlevel = 0
        self.bracelevel = 0
        self.lexer.begin("INITIAL")

    # Build the lexer
    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)
        self.parenstack = (-100, None)
        self.bracestack = (-100, None)
        self.parenlevel = 0
        self.bracelevel = 0
        return self.lexer

    # Test it output
    def test(self, data):
        self.lexer.input(data)
        while True:
            tok = self.lexer.token()
            if not tok:
                break
            print(tok)

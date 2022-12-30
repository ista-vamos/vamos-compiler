import ply.lex as lex


class MyLexer(object):
    literals = ['[', ']', '{', '}', '(', ')', ':', ';', '=', ',', '>', '-', '|', '$', '.', '*']

    # Declare the state
    states = (
        ('CCODE', 'exclusive'),
    )

    # Match the ##. Enter ccode state.
    def t_BEGIN_CCODE(self, t):
        r'\$\$'
        assert(t.lexer.current_state() == "INITIAL")
        t.lexer.push_state('CCODE')  # Enter 'ccode' state
        return t

    def t_CCODE_END(self, t):
        r'\$\$'
        assert(t.lexer.current_state() == "CCODE")
        t.lexer.pop_state()  # Enter INITIAL state
        assert(t.lexer.current_state() == "INITIAL")

    def t_CCODE_STATEMENT_INITIAL(self, t):
        r'\$'
        assert(t.lexer.current_state() == "CCODE")
        t.lexer.push_state('INITIAL')  # Enter 'initial' state


    def t_CCODE_TOKEN(self, t):
        r"[^$]+"
        assert(t.lexer.current_state() == "CCODE")
        t.type = "CCODE_TOKEN"
        return t

    # Ignored characters (whitespace)
    t_CCODE_ignore = " \t\n"

    # For bad characters, we just skip over it
    def t_CCODE_error(self, t):
        t.lexer.skip(1)
        print("error")

    def t_semicol(self, t):
        r";"
        t.type = ";"

        if len(t.lexer.lexstatestack) > 1:
            assert(t.lexer.current_state() == "INITIAL")
            # end code statement
            t.lexer.pop_state()
            assert(t.lexer.current_state() == "CCODE")
        return t

    def t_2dots(self, t):
        r"^:$"
        t.type = ':'
        return t

    def t_comma(self, t):
        r"^,$"
        t.type = ','
        return t

    def t_equal(self, t):
        r"="
        t.type = '='
        return t

    def t_lcurly(self, t):
        r"\{"
        t.type = '{'  # Set token type to the expected literal
        return t

    def t_rcurly(self, t):
        r"\}"
        t.type = '}'  # Set token type to the expected literal
        return t

    def t_lbracket(self, t):
        r"\["
        t.type = '['  # Set token type to the expected literal
        return t

    def t_rbracket(self, t):
        r"\]"
        t.type = ']'  # Set token type to the expected literal
        return t

    def t_lparenthesis(self, t):
        r"\("
        t.type = '('  # Set token type to the expected literal
        return t

    def t_rparenthesis(self, t):
        r"\)"
        t.type = ')'  # Set token type to the expected literal
        return t

    def t_pipe(self, t):
        r"\|"
        t.type = '|'  # Set token type to the expected literal
        return t

    reserved = {
        'if': 'IF',
        'then': 'THEN',
        'else': 'ELSE',
        'stream':"STREAM",
        'type': "TYPE",
        'autodrop': "AUTODROP",
        'infinite': "INFINITE",
        "blocking" : "BLOCKING",
        'drop': "DROP",
        'forward': "FORWARD",
        "on": "ON",
        "done": "DONE",
        "nothing": "NOTHING",
        "yield": "YIELD",
        "switch": "SWITCH",
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
        "fun" : "FUN",
        "choose": "CHOOSE",
        "by" : "BY",
        "remove": "REMOVE",
        "globals" : "GLOBALS",
        "startup": "STARTUP",
        "cleanup": "CLEANUP",
        "processor" : "PROCESSOR",
        "include": "INCLUDE",
        "includes": "INCLUDES",
        "first" : "FIRST",
        "last": "LAST",
        "order": "ORDER",
        "all": "ALL",
        "add": "ADD",
        "in": "IN",
        "count": "COUNT",
        "max": "MAX",
        "min": "MIN",
        "always": "ALWAYS",
        "continue": "CONTINUE"
    }

    # Token names.
    tokens = [
        # data types
        "BOOL", "INT", "ID",
        # ccode
        "CCODE_TOKEN", # matches everything except $
        "BEGIN_CCODE"

    ] + list(reserved.values())

    # Regular expression rules for simple tokens

    # A regular expression rule with some action code
    # Note addition of self parameter since we're in a class
    def t_INT(self, t):
        r'((\-?|\+?)([1-9][0-9]*)|0)'
        t.value = int(t.value)
        return t

    def t_ID(self, t):
        r'[a-zA-Z_][a-zA-Z_0-9]*'
        # for variable names and keywords
        t.type = self.reserved.get(t.value.lower(), 'ID')  # Check for reserved words
        return t


    # Define a rule so we can track line numbers
    def t_newline(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)

    # A string containing ignored characters (spaces and tabs)
    t_ignore = ' \t'

    # Error handling rule
    def t_error(self, t):
        print(f"Illegal character {t.value[0]} (line {t.lexer.lineno}) (pos {t.lexer.lexpos})")
        t.lexer.skip(1)

    # Build the lexer
    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    # Test it output
    def test(self, data):
        self.lexer.input(data)
        while True:
            tok = self.lexer.token()
            if not tok:
                break
            print(tok)

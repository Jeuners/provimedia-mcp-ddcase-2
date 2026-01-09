# HALLUZI_PREVENT - Halluzinations-Prävention für Chainguard

> **Version:** 3.0.0 (Implementiert)
> **Status:** Produktionsreif ✅
> **Ziel:** Verhinderung von halluzinierten Funktionen, Methoden, Variablen und Package-Imports durch LLMs
> **Letzte Aktualisierung:** 2026-01-09
>
> ### ⚠️ WICHTIGES DESIGN-PRINZIP
> **False Positives dürfen NIEMALS den Workflow blockieren!**
> - Default-Mode: `WARN` (zeigt Probleme, blockiert nie)
> - `STRICT` Mode nur wenn User explizit aktiviert
> - Bei Unsicherheit: Warnen statt Blocken
>
> ### v3.0 NEU: Slopsquatting-Detection
> - Package-Import Validierung für PHP/JS/TS/Python
> - Levenshtein-basierte Typo-Erkennung
> - ~20% der LLM-empfohlenen Packages existieren nicht!

---

## 1. Das Problem

### 1.1 Was sind Symbol-Halluzinationen?

LLMs generieren Code basierend auf **Wahrscheinlichkeit**, nicht auf **Wahrheit**. Sie "raten" Funktions- und Variablennamen basierend auf Patterns aus dem Training:

```
┌─────────────────────────────────────────────────────────────┐
│  LLM-Denkprozess:                                          │
│                                                             │
│  "Ich sehe eine User-Klasse..."                            │
│  "Also gibt es wahrscheinlich getUserById()"               │
│  "Und user.userName ist bestimmt das Feld"                 │
│                                                             │
│  → Pattern-Matching aus Training                            │
│  → KEIN Wissen über die echte Codebase                     │
│                                                             │
│  Realität:                                                  │
│  - Funktion heißt findUserById()                           │
│  - Feld heißt user.username (lowercase)                    │
│  → HALLUZINATION!                                          │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Typische Halluzinations-Beispiele

**PHP:**
```php
// LLM schreibt:
$user = $this->userRepository->getUserById($id);  // FALSCH
$user->userName = "Test";                          // FALSCH

// Realität:
$user = $this->userRepository->findById($id);     // Richtig
$user->username = "Test";                          // Richtig
```

**JavaScript/TypeScript:**
```typescript
// LLM schreibt:
const user = await userService.fetchUser(id);     // FALSCH
console.log(user.firstName);                       // FALSCH

// Realität:
const user = await userService.getById(id);       // Richtig
console.log(user.first_name);                      // Richtig
```

**C#:**
```csharp
// LLM schreibt:
var user = await _userService.GetUserById(id);    // FALSCH
await _notificationService.SendNotification(user); // FALSCH

// Realität:
var user = await _userService.FindByIdAsync(id);  // Richtig
await _notificationService.NotifyAsync(user);      // Richtig
```

### 1.3 Warum DB-Schema-Check funktioniert

Chainguard löst das Problem bei Datenbank-Feldern bereits:

```
┌─────────────────────────────────────────────────────────────┐
│  VORHER (ohne Schema):                                      │
│  LLM: SELECT user_name FROM users  ← HALLUZINIERT          │
│                                                             │
│  NACHHER (mit Schema):                                      │
│  chainguard_db_schema() → "users: id, username, email"     │
│  LLM: SELECT username FROM users   ← KORREKT               │
│                                                             │
│  Prinzip: Ground Truth VOR Generierung injizieren          │
└─────────────────────────────────────────────────────────────┘
```

**Dieses Prinzip übertragen wir auf Code-Symbole.**

---

## 2. Die Lösung: Regex-basierte Symbol-Validierung

### 2.1 Kernprinzip

```
┌─────────────────────────────────────────────────────────────┐
│  1. Sprache erkennen (Dateiendung + Syntax-Patterns)       │
│                         ↓                                   │
│  2. Funktionsaufrufe extrahieren (Regex)                   │
│                         ↓                                   │
│  3. Codebase durchsuchen (Grep nach Definition)            │
│                         ↓                                   │
│  4. Report: "getUserById() existiert nicht!"               │
│                         ↓                                   │
│  5. Vorschlag: "Meinten Sie findById()?"                   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Warum Regex statt AST?

| Aspekt | AST-Parser | Regex |
|--------|------------|-------|
| Komplexität | Hoch (pro Sprache ein Parser) | Niedrig |
| Performance | Langsam | Schnell |
| Genauigkeit | 100% | ~90% (reicht für Validierung) |
| Wartung | Aufwändig | Einfach |
| Neue Sprache | Neuer Parser nötig | Neue Patterns hinzufügen |

**Fazit:** Regex ist "good enough" für Symbol-Erkennung und deutlich praktischer.

---

## 3. Regex-Patterns nach Sprache

### 3.1 PHP

```python
CALL_PATTERNS['php'] = [
    # Funktionsaufruf: functionName(...)
    r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',

    # Methodenaufruf: $obj->methodName(...)
    r'->\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',

    # Statischer Aufruf: ClassName::methodName(...)
    r'([A-Z][a-zA-Z0-9_]*)::\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
]

DEFINITION_PATTERNS['php'] = [
    # function name(...) {
    r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',

    # public/private/protected function name(...)
    r'(?:public|private|protected)\s+(?:static\s+)?function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
]

PROPERTY_PATTERNS['php'] = [
    # public $propertyName;
    r'(?:public|private|protected)\s+\$([a-zA-Z_][a-zA-Z0-9_]*)',

    # $this->propertyName
    r'\$this\s*->\s*([a-zA-Z_][a-zA-Z0-9_]*)',
]

BUILTINS['php'] = {
    'isset', 'empty', 'array', 'count', 'strlen', 'print', 'echo',
    'explode', 'implode', 'str_replace', 'preg_match', 'preg_replace',
    'array_map', 'array_filter', 'array_merge', 'array_keys', 'array_values',
    'json_encode', 'json_decode', 'file_get_contents', 'file_put_contents',
    'is_array', 'is_string', 'is_null', 'is_numeric', 'is_object',
    'sprintf', 'printf', 'var_dump', 'print_r', 'die', 'exit',
    'date', 'time', 'strtotime', 'DateTime',
    'trim', 'ltrim', 'rtrim', 'strtolower', 'strtoupper',
    'substr', 'strpos', 'str_contains', 'str_starts_with', 'str_ends_with',
    'intval', 'floatval', 'strval', 'boolval',
    'header', 'session_start', 'setcookie',
    '__construct', '__destruct', '__get', '__set', '__call', '__toString',
}
```

### 3.2 JavaScript

```python
CALL_PATTERNS['javascript'] = [
    # Funktionsaufruf: functionName(...)
    r'\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(',

    # Methodenaufruf: obj.methodName(...)
    r'\.\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(',

    # Optional Chaining: obj?.methodName(...)
    r'\?\.\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(',
]

DEFINITION_PATTERNS['javascript'] = [
    # function name(...) {
    r'function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(',

    # const/let/var name = (...) =>
    r'(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>',

    # const/let/var name = function(...)
    r'(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s+)?function',

    # Klassen-Methode: methodName(...) {
    r'^\s*(?:async\s+)?([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^)]*\)\s*\{',

    # Klassen-Methode mit Modifiern: static async methodName(...)
    r'(?:static\s+)?(?:async\s+)?([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^)]*\)\s*\{',
]

BUILTINS['javascript'] = {
    'console', 'log', 'warn', 'error', 'info', 'debug',
    'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
    'parseInt', 'parseFloat', 'isNaN', 'isFinite',
    'JSON', 'parse', 'stringify',
    'Object', 'keys', 'values', 'entries', 'assign', 'freeze',
    'Array', 'from', 'isArray', 'map', 'filter', 'reduce', 'forEach',
    'find', 'findIndex', 'includes', 'indexOf', 'slice', 'splice',
    'push', 'pop', 'shift', 'unshift', 'concat', 'join', 'sort',
    'String', 'toString', 'toLowerCase', 'toUpperCase', 'trim',
    'split', 'replace', 'match', 'startsWith', 'endsWith', 'includes',
    'Promise', 'resolve', 'reject', 'all', 'allSettled', 'race', 'any',
    'then', 'catch', 'finally',
    'fetch', 'Request', 'Response', 'Headers',
    'Math', 'floor', 'ceil', 'round', 'random', 'max', 'min', 'abs',
    'Date', 'now', 'getTime', 'toISOString',
    'Error', 'TypeError', 'RangeError', 'throw',
    'require', 'module', 'exports', 'import', 'export', 'default',
    'document', 'window', 'localStorage', 'sessionStorage',
    'getElementById', 'querySelector', 'querySelectorAll',
    'addEventListener', 'removeEventListener',
}
```

### 3.3 TypeScript

```python
# TypeScript erbt JavaScript-Patterns und fügt hinzu:

CALL_PATTERNS['typescript'] = CALL_PATTERNS['javascript'] + [
    # Generischer Aufruf: methodName<Type>(...)
    r'\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*<[^>]+>\s*\(',
]

DEFINITION_PATTERNS['typescript'] = DEFINITION_PATTERNS['javascript'] + [
    # Typed function: function name(arg: Type): ReturnType {
    r'function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:<[^>]+>)?\s*\([^)]*\)\s*:\s*\w+',

    # Interface method: methodName(arg: Type): ReturnType;
    r'^\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:<[^>]+>)?\s*\([^)]*\)\s*:\s*\w+\s*;',
]

BUILTINS['typescript'] = BUILTINS['javascript'] | {
    'Partial', 'Required', 'Readonly', 'Pick', 'Omit', 'Record',
    'Exclude', 'Extract', 'NonNullable', 'ReturnType', 'Parameters',
    'keyof', 'typeof', 'instanceof', 'as', 'is',
}
```

### 3.4 Python

```python
CALL_PATTERNS['python'] = [
    # Funktionsaufruf: function_name(...)
    r'\b([a-z_][a-z0-9_]*)\s*\(',

    # Methodenaufruf: obj.method_name(...)
    r'\.\s*([a-z_][a-z0-9_]*)\s*\(',

    # Klassen-Instanziierung: ClassName(...)
    r'\b([A-Z][a-zA-Z0-9_]*)\s*\(',
]

DEFINITION_PATTERNS['python'] = [
    # def function_name(...):
    r'def\s+([a-z_][a-z0-9_]*)\s*\(',

    # async def function_name(...):
    r'async\s+def\s+([a-z_][a-z0-9_]*)\s*\(',

    # class ClassName:
    r'class\s+([A-Z][a-zA-Z0-9_]*)\s*[:\(]',
]

PROPERTY_PATTERNS['python'] = [
    # self.property_name = ...
    r'self\s*\.\s*([a-z_][a-z0-9_]*)\s*=',

    # self.property_name (Zugriff)
    r'self\s*\.\s*([a-z_][a-z0-9_]*)',
]

BUILTINS['python'] = {
    'print', 'len', 'range', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple',
    'type', 'isinstance', 'issubclass', 'hasattr', 'getattr', 'setattr', 'delattr',
    'open', 'read', 'write', 'close', 'with', 'as',
    'map', 'filter', 'reduce', 'zip', 'enumerate', 'sorted', 'reversed',
    'sum', 'min', 'max', 'abs', 'round', 'pow', 'divmod',
    'all', 'any', 'iter', 'next', 'callable',
    'format', 'repr', 'ascii', 'chr', 'ord', 'hex', 'oct', 'bin',
    'id', 'hash', 'dir', 'vars', 'globals', 'locals',
    'input', 'exit', 'quit', 'help',
    'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError', 'AttributeError',
    'super', 'property', 'classmethod', 'staticmethod',
    '__init__', '__str__', '__repr__', '__call__', '__getitem__', '__setitem__',
    '__len__', '__iter__', '__next__', '__enter__', '__exit__',
}
```

### 3.5 C#

```python
CALL_PATTERNS['csharp'] = [
    # Einfacher Aufruf: MethodName(...)
    r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(',

    # Methodenaufruf: obj.MethodName(...)
    r'\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(',

    # Statischer Aufruf: ClassName.MethodName(...)
    r'([A-Z][A-Za-z0-9_]*)\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(',

    # Generischer Aufruf: MethodName<Type>(...)
    r'\b([A-Za-z_][A-Za-z0-9_]*)\s*<[^>]+>\s*\(',

    # Await: await MethodName(...)
    r'await\s+(?:\w+\s*\.\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(',

    # Null-conditional: obj?.MethodName(...)
    r'\?\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(',
]

DEFINITION_PATTERNS['csharp'] = [
    # Standard-Methode: public void MethodName(...)
    r'(?:public|private|protected|internal)\s+'
    r'(?:static\s+)?'
    r'(?:async\s+)?'
    r'(?:override\s+)?'
    r'(?:virtual\s+)?'
    r'(?:abstract\s+)?'
    r'(?:\w+(?:<[^>]+>)?)\s+'
    r'([A-Z][A-Za-z0-9_]*)\s*'
    r'(?:<[^>]+>)?\s*\(',

    # Konstruktor: public ClassName(...)
    r'(?:public|private|protected|internal)\s+'
    r'([A-Z][A-Za-z0-9_]*)\s*\([^)]*\)\s*(?::|{)',

    # Expression-bodied: public int GetValue() =>
    r'(?:public|private|protected|internal)\s+'
    r'(?:static\s+)?'
    r'(?:\w+(?:<[^>]+>)?)\s+'
    r'([A-Z][A-Za-z0-9_]*)\s*\([^)]*\)\s*=>',

    # Interface-Methode
    r'^\s*(?:\w+(?:<[^>]+>)?)\s+([A-Z][A-Za-z0-9_]*)\s*\([^)]*\)\s*;',
]

PROPERTY_PATTERNS['csharp'] = [
    # Auto-Property: public string Name { get; set; }
    r'(?:public|private|protected|internal)\s+'
    r'(?:static\s+)?'
    r'(?:virtual\s+)?'
    r'(?:\w+(?:<[^>]+>)?)\s+'
    r'([A-Z][A-Za-z0-9_]*)\s*'
    r'\{\s*get',

    # Field: private int _fieldName;
    r'(?:private|protected)\s+'
    r'(?:readonly\s+)?'
    r'(?:\w+(?:<[^>]+>)?)\s+'
    r'(_[a-z][A-Za-z0-9_]*)\s*[;=]',
]

BUILTINS['csharp'] = {
    # System
    'ToString', 'GetType', 'Equals', 'GetHashCode', 'ReferenceEquals',
    'Console', 'WriteLine', 'ReadLine', 'Write', 'Read',

    # Collections
    'Add', 'Remove', 'Contains', 'Clear', 'Count', 'Length',
    'First', 'Last', 'Where', 'Select', 'OrderBy', 'OrderByDescending',
    'GroupBy', 'Join', 'Distinct', 'Union', 'Intersect', 'Except',
    'ToList', 'ToArray', 'ToDictionary', 'ToHashSet',
    'Any', 'All', 'Sum', 'Average', 'Min', 'Max', 'Count',
    'FirstOrDefault', 'LastOrDefault', 'SingleOrDefault',
    'Skip', 'Take', 'SkipWhile', 'TakeWhile',
    'Aggregate', 'Zip', 'SelectMany', 'Concat',

    # String
    'Format', 'Join', 'Split', 'Trim', 'TrimStart', 'TrimEnd',
    'Replace', 'Remove', 'Insert', 'PadLeft', 'PadRight',
    'StartsWith', 'EndsWith', 'Contains', 'IndexOf', 'LastIndexOf',
    'Substring', 'ToLower', 'ToUpper', 'ToCharArray',
    'IsNullOrEmpty', 'IsNullOrWhiteSpace', 'Concat', 'Compare',

    # Async/Task
    'Task', 'ConfigureAwait', 'Wait', 'Result', 'GetAwaiter', 'GetResult',
    'WhenAll', 'WhenAny', 'Delay', 'Run', 'FromResult',
    'ContinueWith', 'CancellationToken', 'CancellationTokenSource',

    # Common Types
    'Parse', 'TryParse', 'Convert', 'ToString',
    'DateTime', 'Now', 'Today', 'UtcNow', 'AddDays', 'AddHours',
    'TimeSpan', 'FromSeconds', 'FromMinutes', 'FromHours',
    'Guid', 'NewGuid', 'Empty', 'Parse',
    'Math', 'Abs', 'Floor', 'Ceiling', 'Round', 'Max', 'Min', 'Pow', 'Sqrt',

    # IO
    'File', 'Exists', 'ReadAllText', 'WriteAllText', 'ReadAllLines',
    'Directory', 'CreateDirectory', 'Delete', 'Move', 'Copy',
    'Path', 'Combine', 'GetFileName', 'GetDirectoryName', 'GetExtension',
    'Stream', 'StreamReader', 'StreamWriter', 'MemoryStream',

    # DI / ASP.NET Core
    'GetService', 'GetRequiredService', 'CreateScope',
    'AddScoped', 'AddTransient', 'AddSingleton', 'AddDbContext',
    'Configure', 'AddOptions', 'Bind', 'Get',
    'UseRouting', 'UseEndpoints', 'UseAuthentication', 'UseAuthorization',
    'MapControllers', 'MapGet', 'MapPost', 'MapPut', 'MapDelete',
    'AddControllers', 'AddMvc', 'AddRazorPages',

    # Entity Framework
    'DbContext', 'DbSet', 'SaveChanges', 'SaveChangesAsync',
    'Include', 'ThenInclude', 'AsNoTracking', 'AsQueryable',
    'Find', 'FindAsync', 'Add', 'AddAsync', 'Update', 'Remove',

    # JSON
    'JsonSerializer', 'Serialize', 'Deserialize', 'SerializeAsync',
    'JsonConvert', 'SerializeObject', 'DeserializeObject',
}
```

### 3.6 Go

```python
CALL_PATTERNS['go'] = [
    # Funktionsaufruf: functionName(...)
    r'\b([a-z][a-zA-Z0-9]*)\s*\(',

    # Exportierte Funktion: FunctionName(...)
    r'\b([A-Z][a-zA-Z0-9]*)\s*\(',

    # Methodenaufruf: obj.MethodName(...)
    r'\.\s*([A-Z][a-zA-Z0-9]*)\s*\(',

    # Package-Aufruf: pkg.FunctionName(...)
    r'([a-z][a-zA-Z0-9]*)\s*\.\s*([A-Z][a-zA-Z0-9]*)\s*\(',
]

DEFINITION_PATTERNS['go'] = [
    # func functionName(...) {
    r'func\s+([a-zA-Z][a-zA-Z0-9]*)\s*\(',

    # func (r *Receiver) MethodName(...) {
    r'func\s+\([^)]+\)\s+([A-Z][a-zA-Z0-9]*)\s*\(',

    # type StructName struct {
    r'type\s+([A-Z][a-zA-Z0-9]*)\s+struct\s*\{',

    # type InterfaceName interface {
    r'type\s+([A-Z][a-zA-Z0-9]*)\s+interface\s*\{',
]

BUILTINS['go'] = {
    'fmt', 'Println', 'Printf', 'Sprintf', 'Errorf', 'Fprintf',
    'make', 'new', 'len', 'cap', 'append', 'copy', 'delete', 'close',
    'panic', 'recover', 'print', 'println',
    'error', 'Error', 'New', 'Unwrap', 'Is', 'As',
    'string', 'int', 'int64', 'float64', 'bool', 'byte', 'rune',
    'nil', 'true', 'false', 'iota',
    'context', 'Background', 'TODO', 'WithCancel', 'WithTimeout', 'WithValue',
    'http', 'Get', 'Post', 'NewRequest', 'ListenAndServe',
    'json', 'Marshal', 'Unmarshal', 'NewEncoder', 'NewDecoder',
    'io', 'Reader', 'Writer', 'ReadAll', 'Copy', 'EOF',
    'os', 'Open', 'Create', 'Remove', 'Mkdir', 'Getenv', 'Exit',
    'strings', 'Contains', 'HasPrefix', 'HasSuffix', 'Split', 'Join', 'Replace',
    'strconv', 'Itoa', 'Atoi', 'ParseInt', 'ParseFloat',
    'time', 'Now', 'Sleep', 'Since', 'Until', 'Duration', 'Second', 'Minute',
    'sync', 'Mutex', 'RWMutex', 'WaitGroup', 'Once', 'Map',
    'log', 'Fatal', 'Fatalf', 'Panic', 'Panicf',
}
```

### 3.7 Rust

```python
CALL_PATTERNS['rust'] = [
    # Funktionsaufruf: function_name(...)
    r'\b([a-z_][a-z0-9_]*)\s*\(',

    # Methodenaufruf: obj.method_name(...)
    r'\.\s*([a-z_][a-z0-9_]*)\s*\(',

    # Turbofish: function_name::<Type>(...)
    r'\b([a-z_][a-z0-9_]*)\s*::\s*<[^>]+>\s*\(',

    # Associated function: Type::function_name(...)
    r'([A-Z][a-zA-Z0-9]*)\s*::\s*([a-z_][a-z0-9_]*)\s*\(',

    # Macro: macro_name!(...)
    r'\b([a-z_][a-z0-9_]*)\s*!\s*[(\[]',
]

DEFINITION_PATTERNS['rust'] = [
    # fn function_name(...) {
    r'fn\s+([a-z_][a-z0-9_]*)\s*(?:<[^>]+>)?\s*\(',

    # pub fn function_name(...) {
    r'pub\s+(?:async\s+)?fn\s+([a-z_][a-z0-9_]*)\s*(?:<[^>]+>)?\s*\(',

    # impl StructName { ... }
    r'impl\s+(?:<[^>]+>\s+)?([A-Z][a-zA-Z0-9]*)',

    # struct StructName {
    r'(?:pub\s+)?struct\s+([A-Z][a-zA-Z0-9]*)',

    # enum EnumName {
    r'(?:pub\s+)?enum\s+([A-Z][a-zA-Z0-9]*)',

    # trait TraitName {
    r'(?:pub\s+)?trait\s+([A-Z][a-zA-Z0-9]*)',
]

BUILTINS['rust'] = {
    'println', 'print', 'eprintln', 'eprint', 'format', 'write', 'writeln',
    'panic', 'assert', 'assert_eq', 'assert_ne', 'debug_assert',
    'vec', 'Vec', 'new', 'with_capacity', 'push', 'pop', 'len', 'is_empty',
    'String', 'from', 'to_string', 'as_str', 'chars', 'bytes',
    'Option', 'Some', 'None', 'unwrap', 'unwrap_or', 'unwrap_or_else', 'map', 'and_then',
    'Result', 'Ok', 'Err', 'expect', 'is_ok', 'is_err',
    'Box', 'Rc', 'Arc', 'RefCell', 'Mutex', 'RwLock',
    'Clone', 'clone', 'Copy', 'Default', 'default',
    'Iterator', 'iter', 'iter_mut', 'into_iter', 'collect', 'filter', 'map', 'fold',
    'for_each', 'enumerate', 'zip', 'take', 'skip', 'chain', 'flatten',
    'impl', 'self', 'Self', 'super', 'crate', 'mod', 'use', 'pub',
    'async', 'await', 'Future', 'poll', 'Pin',
    'drop', 'Drop', 'mem', 'swap', 'replace', 'take',
    'cfg', 'feature', 'test', 'derive', 'allow', 'warn', 'deny',
}
```

---

## 4. Der Algorithmus

### 4.1 Klassen-Struktur

```python
# symbol_validator.py

from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from difflib import get_close_matches
import re

@dataclass
class SymbolLocation:
    """Ort einer Symbol-Definition."""
    file: str
    line: int
    symbol_type: str  # 'function', 'method', 'class', 'property'

@dataclass
class UnknownSymbol:
    """Ein nicht gefundenes Symbol."""
    name: str
    file: str
    line: int
    similar: List[str]
    locations: List[SymbolLocation]

class SymbolValidator:
    """Regex-basierte Validierung von Code-Symbolen."""

    LANGUAGE_MAP = {
        '.php': 'php',
        '.js': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript', '.jsx': 'javascript',
        '.ts': 'typescript', '.tsx': 'typescript',
        '.py': 'python',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
    }

    EXCLUDE_DIRS = {
        'vendor', 'node_modules', '.git', '__pycache__',
        'bin', 'obj', 'target', 'dist', 'build',
    }

    EXCLUDE_FILES = {
        '.min.js', '.min.css', '.d.ts', '.Designer.cs', '.g.cs',
        '.blade.php',  # Blade Templates separat behandeln
    }

    def __init__(self, codebase_path: str):
        self.codebase_path = Path(codebase_path)
        self.defined_symbols: Dict[str, List[SymbolLocation]] = {}
        self._scanned = False

    def detect_language(self, file_path: str) -> Optional[str]:
        """Erkennt Sprache anhand Dateiendung."""
        path = Path(file_path)

        # Exclude-Check
        for exclude in self.EXCLUDE_FILES:
            if str(path).endswith(exclude):
                return None

        return self.LANGUAGE_MAP.get(path.suffix.lower())

    def _should_skip_dir(self, path: Path) -> bool:
        """Prüft ob Verzeichnis übersprungen werden soll."""
        return any(exclude in path.parts for exclude in self.EXCLUDE_DIRS)

    def scan_codebase(self) -> int:
        """
        Scannt die gesamte Codebase nach Funktionsdefinitionen.
        Returns: Anzahl gefundener Symbole.
        """
        if self._scanned:
            return len(self.defined_symbols)

        for ext, lang in self.LANGUAGE_MAP.items():
            for file in self.codebase_path.rglob(f"*{ext}"):
                if self._should_skip_dir(file):
                    continue

                try:
                    content = file.read_text(encoding='utf-8', errors='ignore')
                    definitions = self._extract_definitions(content, lang)

                    rel_path = str(file.relative_to(self.codebase_path))

                    for name, line_no, sym_type in definitions:
                        location = SymbolLocation(rel_path, line_no, sym_type)
                        self.defined_symbols.setdefault(name, []).append(location)

                except Exception as e:
                    # Log but continue
                    pass

        self._scanned = True
        return len(self.defined_symbols)

    def _extract_definitions(self, content: str, lang: str) -> List[Tuple[str, int, str]]:
        """
        Extrahiert alle Symbol-Definitionen aus Code.
        Returns: Liste von (name, line_number, type) Tupeln.
        """
        results = []
        patterns = DEFINITION_PATTERNS.get(lang, [])

        lines = content.split('\n')
        for line_no, line in enumerate(lines, 1):
            # Skip Kommentare
            stripped = line.strip()
            if stripped.startswith(('#', '//', '/*', '*', '"""', "'''")):
                continue

            for pattern in patterns:
                for match in re.finditer(pattern, line, re.IGNORECASE):
                    name = match.group(1)
                    sym_type = self._detect_symbol_type(pattern, line)
                    results.append((name, line_no, sym_type))

        return results

    def _extract_calls(self, content: str, lang: str) -> List[Tuple[str, int]]:
        """
        Extrahiert alle Funktionsaufrufe aus Code.
        Returns: Liste von (name, line_number) Tupeln.
        """
        results = []
        patterns = CALL_PATTERNS.get(lang, [])
        builtins = BUILTINS.get(lang, set())

        lines = content.split('\n')
        for line_no, line in enumerate(lines, 1):
            # Skip Kommentare
            stripped = line.strip()
            if stripped.startswith(('#', '//', '/*', '*', '"""', "'''")):
                continue

            # Skip Import/Using Statements
            if self._is_import_line(stripped, lang):
                continue

            for pattern in patterns:
                for match in re.finditer(pattern, line):
                    # Hole das letzte erfasste Group (für mehrstufige Patterns)
                    groups = [g for g in match.groups() if g]
                    if not groups:
                        continue
                    name = groups[-1]  # Letztes Match ist meist der Funktionsname

                    # Skip builtins
                    if name in builtins:
                        continue

                    # Skip Konstruktoren (PascalCase in manchen Sprachen)
                    if self._is_constructor_call(name, lang):
                        continue

                    results.append((name, line_no))

        return results

    def _is_import_line(self, line: str, lang: str) -> bool:
        """Erkennt Import-Statements."""
        import_patterns = {
            'php': r'^(use|require|include)',
            'javascript': r'^(import|require|export)',
            'typescript': r'^(import|require|export)',
            'python': r'^(import|from)',
            'csharp': r'^using\s+',
            'go': r'^(import|package)',
            'rust': r'^(use|mod|extern)',
        }
        pattern = import_patterns.get(lang)
        if pattern:
            return bool(re.match(pattern, line, re.IGNORECASE))
        return False

    def _is_constructor_call(self, name: str, lang: str) -> bool:
        """
        Erkennt ob es sich um einen Konstruktor-Aufruf handelt.
        Konstruktoren sind OK, da sie Klassen sind (neue Instanzen).
        """
        # In PHP/C#/Java sind Konstruktoren PascalCase
        if lang in ('csharp', 'php', 'java'):
            return name[0].isupper() if name else False
        # In JS: new ClassName() - hier ist ClassName OK
        if lang in ('javascript', 'typescript'):
            return name[0].isupper() if name else False
        return False

    def _detect_symbol_type(self, pattern: str, line: str) -> str:
        """Erkennt den Typ des Symbols anhand des Patterns."""
        if 'class' in pattern.lower() or 'struct' in line.lower():
            return 'class'
        if 'interface' in line.lower() or 'trait' in line.lower():
            return 'interface'
        if '->' in pattern or 'self.' in pattern or 'this.' in pattern:
            return 'method'
        return 'function'

    def validate_file(self, file_path: str) -> List[UnknownSymbol]:
        """
        Prüft ob alle Funktionsaufrufe in einer Datei existieren.
        Returns: Liste von nicht gefundenen Symbolen.
        """
        self.scan_codebase()  # Lazy scan

        lang = self.detect_language(file_path)
        if not lang:
            return []

        try:
            content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return []

        calls = self._extract_calls(content, lang)

        issues = []
        checked: Set[str] = set()  # Deduplizieren

        for name, line_no in calls:
            if name in checked:
                continue
            checked.add(name)

            if name not in self.defined_symbols:
                # Ähnliche finden für Vorschläge
                similar = get_close_matches(
                    name,
                    self.defined_symbols.keys(),
                    n=3,
                    cutoff=0.6
                )

                # Locations für ähnliche Symbole
                locations = []
                for s in similar[:3]:
                    if s in self.defined_symbols:
                        locations.extend(self.defined_symbols[s][:1])

                issues.append(UnknownSymbol(
                    name=name,
                    file=file_path,
                    line=line_no,
                    similar=similar,
                    locations=locations
                ))

        return issues

    def quality_check(self, changed_files: List[str]) -> Tuple[bool, str]:
        """
        Batch-Prüfung aller geänderten Dateien.
        Returns: (passed, report_text)
        """
        all_issues: List[UnknownSymbol] = []

        for file in changed_files:
            issues = self.validate_file(file)
            all_issues.extend(issues)

        if not all_issues:
            return True, "✓ Symbol Quality Check: All functions verified"

        # Format Report
        lines = [f"⚠️ Symbol Quality Check: {len(all_issues)} potential issues\n"]

        for issue in all_issues[:10]:  # Max 10 anzeigen
            lines.append(f"  • {issue.name}() in {issue.file}:{issue.line}")
            if issue.similar:
                suggestions = ', '.join(issue.similar)
                lines.append(f"    → Did you mean: {suggestions}?")
                if issue.locations:
                    loc = issue.locations[0]
                    lines.append(f"      Found in: {loc.file}:{loc.line}")

        if len(all_issues) > 10:
            lines.append(f"\n  ... and {len(all_issues) - 10} more issues")

        return False, '\n'.join(lines)
```

### 4.2 Integration in Chainguard

```python
# In handlers.py - chainguard_finish erweitern

@handler.register("chainguard_finish")
async def handle_finish(args: Dict[str, Any]) -> List[TextContent]:
    state = await get_current_state()

    # ... existing completion checks ...

    # NEU: Symbol Quality Check (nur im Programming-Mode)
    if state.mode == TaskMode.PROGRAMMING:
        symbol_check_enabled = config.get("SYMBOL_CHECK_ENABLED", True)

        if symbol_check_enabled and state.changed_files:
            from .symbol_validator import SymbolValidator

            validator = SymbolValidator(state.working_dir)
            passed, report = validator.quality_check(list(state.changed_files))

            if not passed:
                response_parts.append(report)

                if not args.get("force", False):
                    response_parts.append(
                        "\n⚠️ Symbol validation found issues."
                        "\nUse force=True to complete anyway."
                    )
                    return [TextContent(type="text", text="\n".join(response_parts))]

    # ... rest of finish logic ...
```

### 4.3 Konfiguration

```python
# In config.py

# Symbol Validation Feature
SYMBOL_CHECK_ENABLED = True  # Feature aktivieren/deaktivieren
SYMBOL_CHECK_STRICT = False  # True = Block bei Fehlern, False = nur Warning
SYMBOL_SIMILARITY_CUTOFF = 0.6  # Mindest-Ähnlichkeit für Vorschläge
SYMBOL_MAX_SUGGESTIONS = 3  # Max. Anzahl Vorschläge
SYMBOL_MAX_ISSUES_DISPLAY = 10  # Max. angezeigte Issues im Report
```

---

## 5. Anwendungsbeispiele

### 5.1 PHP Projekt

```
Session:
1. chainguard_set_scope(description="Auth erweitern", modules=["app/Http/**"])
2. Edit: app/Http/Controllers/AuthController.php
3. chainguard_track(file="app/Http/Controllers/AuthController.php")
4. chainguard_finish()

Output:
⚠️ Symbol Quality Check: 2 potential issues

  • getUserById() in app/Http/Controllers/AuthController.php:45
    → Did you mean: findById, getById, findUserById?
      Found in: app/Repositories/UserRepository.php:23

  • sendNotification() in app/Http/Controllers/AuthController.php:67
    → Did you mean: sendEmail, notify, dispatch?
      Found in: app/Services/NotificationService.php:15

⚠️ Symbol validation found issues.
Use force=True to complete anyway.
```

### 5.2 TypeScript Projekt

```
Session:
1. chainguard_set_scope(description="API Client", modules=["src/services/**"])
2. Edit: src/services/UserService.ts
3. chainguard_track(file="src/services/UserService.ts")
4. chainguard_finish()

Output:
⚠️ Symbol Quality Check: 1 potential issue

  • fetchUserData() in src/services/UserService.ts:34
    → Did you mean: getUserData, fetchUser, loadUser?
      Found in: src/api/userApi.ts:12

⚠️ Symbol validation found issues.
Use force=True to complete anyway.
```

### 5.3 C# Projekt

```
Session:
1. chainguard_set_scope(description="Repository Pattern", modules=["src/Data/**"])
2. Edit: src/Data/Repositories/UserRepository.cs
3. chainguard_track(file="src/Data/Repositories/UserRepository.cs")
4. chainguard_finish()

Output:
✓ Symbol Quality Check: All functions verified
✓ All acceptance criteria fulfilled
✓ Task completed successfully
```

---

## 6. Grenzen und False Positives

### 6.1 Bekannte Einschränkungen

| Szenario | Problem | Lösung |
|----------|---------|--------|
| Dynamische Aufrufe | `$this->$method()` nicht erkennbar | Ignorieren |
| Reflection | `Type.GetMethod("Name")` | Ignorieren |
| String-Callbacks | `array_map('strtolower', $arr)` | Whitelist |
| Externe Libraries | `$client->request()` | Import-Tracking |
| Generierte Dateien | `.Designer.cs` | Exclude-Liste |
| Metaprogrammierung | Ruby/Python Metaclasses | Nicht unterstützt |

### 6.2 Ignore-Patterns

```python
# Patterns die ignoriert werden sollen
IGNORE_PATTERNS = {
    'php': [
        r'array_map\s*\(\s*[\'"]',       # array_map('callback', ...)
        r'call_user_func',                # call_user_func(...)
        r'\$\w+\s*\(',                    # $variable() - dynamischer Aufruf
    ],
    'javascript': [
        r'\[\s*[\'"][^\'"]+[\'"]\s*\]',  # obj['dynamicMethod']()
        r'eval\s*\(',                     # eval(...)
        r'new\s+Function\s*\(',           # new Function(...)
    ],
    'csharp': [
        r'GetMethod\s*\(\s*[\'"]',        # Type.GetMethod("name")
        r'Invoke\s*\(',                   # delegate.Invoke(...)
        r'DynamicInvoke\s*\(',            # delegate.DynamicInvoke(...)
    ],
}
```

### 6.3 Whitelist für bekannte externe Symbole

```python
# Bekannte externe Libraries deren Methoden wir ignorieren
EXTERNAL_LIBRARY_PATTERNS = {
    'php': {
        'Guzzle': ['request', 'get', 'post', 'put', 'delete'],
        'Laravel': ['make', 'bind', 'singleton', 'instance'],
        'Doctrine': ['find', 'findBy', 'findOneBy', 'persist', 'flush'],
    },
    'javascript': {
        'axios': ['get', 'post', 'put', 'delete', 'request'],
        'lodash': ['map', 'filter', 'reduce', 'find', 'groupBy'],
        'express': ['get', 'post', 'put', 'delete', 'use', 'listen'],
    },
    'csharp': {
        'EntityFramework': ['Include', 'ThenInclude', 'AsNoTracking'],
        'AutoMapper': ['Map', 'ProjectTo'],
        'MediatR': ['Send', 'Publish'],
    },
}
```

---

## 7. Roadmap

### Phase 1: MVP (Aktuell)
- [x] Konzept dokumentiert
- [ ] `symbol_validator.py` implementieren
- [ ] Integration in `chainguard_finish()`
- [ ] Tests schreiben

### Phase 2: Erweiterungen
- [ ] Property/Variable-Validierung
- [ ] Import-Tracking (externe Libraries erkennen)
- [ ] Namespace-Aware Suche (C#, PHP)
- [ ] Cache für Symbol-Tabelle (Performance)

### Phase 3: Erweitert
- [ ] LSP-Integration als Alternative zu Regex
- [ ] Pre-Edit Injection (Symbole VOR Generierung zeigen)
- [ ] Cross-Project Symbol-Suche
- [ ] IDE-Plugin Integration

---

## 8. Dateien

| Datei | Zweck |
|-------|-------|
| `src/mcp-server/chainguard/symbol_validator.py` | Haupt-Implementierung |
| `src/mcp-server/chainguard/symbol_patterns.py` | Regex-Patterns (optional, kann in validator) |
| `src/mcp-server/tests/test_symbol_validator.py` | Unit-Tests |
| `HALLUZI_PREVENT.md` | Diese Dokumentation |

---

## 9. Zusammenfassung

**Das Symbol-Validierungssystem verhindert Halluzinationen durch:**

1. **Regex-Extraktion** aller Funktionsaufrufe aus geändertem Code
2. **Codebase-Scan** nach existierenden Funktionsdefinitionen
3. **Cross-Reference** zwischen Aufrufen und Definitionen
4. **Fuzzy-Matching** für hilfreiche Vorschläge
5. **Quality-Check** am Ende jeder Session

**Unterstützte Sprachen:** PHP, JavaScript, TypeScript, Python, C#, Go, Rust

**Prinzip:** Gleicher Ansatz wie DB-Schema-Check - Ground Truth gegen Halluzination.

---

## 10. Erweiterte Verbesserungen (v2.0)

Diese Verbesserungen adressieren kritische Lücken im Basis-Konzept und beschreiben die konkrete Implementierung im Kontext der Chainguard MCP-Architektur.

---

### 10.1 Session-Aware Symbol Tracking (Neue Funktionen)

#### Problem
```
LLM schreibt neue Funktion calculateTotal() in File A
LLM ruft calculateTotal() in File B auf
→ Validator: "calculateTotal() nicht gefunden!" (FALSE POSITIVE)
```

#### Lösung: Session-Symbole tracken

**Architektur-Integration:**

```
┌─────────────────────────────────────────────────────────────┐
│  models.py - ProjectState erweitern                        │
│                                                             │
│  @dataclass                                                 │
│  class ProjectState:                                        │
│      # ... existing fields ...                              │
│      session_defined_symbols: Set[str] = field(default_factory=set)  │
│      session_symbol_locations: Dict[str, SymbolLocation] = field(...) │
└─────────────────────────────────────────────────────────────┘
```

**Implementierung in handlers.py:**

```python
# handlers.py - chainguard_track erweitern

@handler.register("chainguard_track")
async def handle_track(args: Dict[str, Any]) -> List[TextContent]:
    file_path = args.get("file")
    state = await get_current_state()

    # ... existing validation logic ...

    # NEU: Extrahiere neue Definitionen aus dieser Datei
    if config.SYMBOL_CHECK_ENABLED:
        content = Path(file_path).read_text(encoding='utf-8')
        lang = detect_language(file_path)

        if lang:
            from .symbol_validator import extract_definitions
            new_defs = extract_definitions(content, lang)

            for name, line, sym_type in new_defs:
                state.session_defined_symbols.add(name)
                state.session_symbol_locations[name] = SymbolLocation(
                    file=file_path, line=line, symbol_type=sym_type
                )

    # ... rest of track logic ...
```

**Implementierung in symbol_validator.py:**

```python
class SymbolValidator:
    def __init__(self, codebase_path: str, session_symbols: Set[str] = None):
        self.codebase_path = Path(codebase_path)
        self.session_symbols = session_symbols or set()  # NEU
        self.defined_symbols: Dict[str, List[SymbolLocation]] = {}

    def validate_call(self, name: str) -> bool:
        # 1. Session-Symbole sind IMMER OK (neu erstellt)
        if name in self.session_symbols:
            return True

        # 2. Codebase-Symbole prüfen
        return name in self.defined_symbols
```

**Dateien die geändert werden:**
| Datei | Änderung |
|-------|----------|
| `models.py` | `session_defined_symbols`, `session_symbol_locations` Fields |
| `handlers.py` | `handle_track()` erweitern |
| `symbol_validator.py` | Constructor + `validate_call()` |

---

### 10.2 Same-File Property Check (Neue Variablen)

#### Problem
```php
// LLM fügt hinzu:
private $userCache;           // Neue Property

// LLM nutzt später:
$this->userCache = [];        // Validator: "userCache nicht gefunden!"
```

#### Lösung: Lokale Definitionen zuerst prüfen

**Implementierung in symbol_validator.py:**

```python
def validate_file(self, file_path: str) -> List[UnknownSymbol]:
    content = Path(file_path).read_text(encoding='utf-8')
    lang = self.detect_language(file_path)

    # 1. LOKALE Definitionen extrahieren (aus diesem File)
    local_definitions = self._extract_definitions(content, lang)
    local_symbols = {d[0] for d in local_definitions}

    # 2. LOKALE Properties extrahieren
    local_properties = self._extract_properties(content, lang)
    local_symbols.update(p[0] for p in local_properties)

    # 3. Aufrufe extrahieren
    calls = self._extract_calls(content, lang)

    issues = []
    for name, line_no in calls:
        # Lokal definiert? → OK, überspringen
        if name in local_symbols:
            continue

        # Session-definiert? → OK, überspringen
        if name in self.session_symbols:
            continue

        # Codebase prüfen
        if name not in self.defined_symbols:
            issues.append(self._create_issue(name, file_path, line_no))

    return issues

def _extract_properties(self, content: str, lang: str) -> List[Tuple[str, int]]:
    """Extrahiert Property-Definitionen."""
    results = []
    patterns = PROPERTY_PATTERNS.get(lang, [])

    for line_no, line in enumerate(content.split('\n'), 1):
        for pattern in patterns:
            for match in re.finditer(pattern, line):
                name = match.group(1)
                results.append((name, line_no))

    return results
```

**Architektur-Diagramm:**

```
┌─────────────────────────────────────────────────────────────┐
│                    VALIDATION HIERARCHY                     │
│                                                             │
│  Symbol gefunden?                                           │
│       │                                                     │
│       ├──▶ 1. Lokal (same file)?     ──▶ ✓ OK              │
│       │                                                     │
│       ├──▶ 2. Session (neu erstellt)? ──▶ ✓ OK             │
│       │                                                     │
│       ├──▶ 3. Codebase (existierend)? ──▶ ✓ OK             │
│       │                                                     │
│       └──▶ 4. Nicht gefunden         ──▶ ⚠️ Issue          │
└─────────────────────────────────────────────────────────────┘
```

---

### 10.3 Confidence-Score System (False Positives vermeiden)

#### Problem
```
Validator meldet 5 "Fehler"
3 davon sind False Positives (externe Libs, dynamisch)
User muss jedes Mal force=True verwenden → FRUSTRIEREND
```

#### Lösung: Confidence-basierte Bewertung

**Neues Dataclass in models.py:**

```python
# models.py

@dataclass
class SymbolIssue:
    """Ein Symbol-Problem mit Confidence-Score."""
    name: str
    file: str
    line: int
    confidence: float  # 0.0 - 1.0
    reason: str        # "not_found", "similar_exists", "possibly_external"
    similar: List[str] = field(default_factory=list)
    locations: List[SymbolLocation] = field(default_factory=list)

    @property
    def severity(self) -> str:
        if self.confidence > 0.8:
            return "HIGH"
        elif self.confidence > 0.5:
            return "MEDIUM"
        return "LOW"
```

**Implementierung in symbol_validator.py:**

```python
class ConfidenceCalculator:
    """Berechnet Confidence-Score für Symbol-Issues."""

    EXTERNAL_INDICATORS = {
        'php': [r'^\$\w+\s*->\s*\w+\s*\(', r'::\w+\s*\('],  # Methoden-Aufrufe
        'javascript': [r'\.\w+\s*\('],  # Methoden-Aufrufe
        'csharp': [r'\.\w+\s*\(', r'\.\w+Async\s*\('],
    }

    COMMON_EXTERNAL_NAMES = {
        # HTTP/API
        'request', 'response', 'get', 'post', 'put', 'delete', 'patch',
        'fetch', 'send', 'call', 'invoke', 'dispatch',

        # Repository/ORM Pattern (WICHTIG für Laravel, Doctrine, EF, etc.)
        'find', 'findById', 'findOne', 'findAll', 'findBy', 'findWhere',
        'findOrFail', 'findFirst', 'findLast', 'firstOrCreate', 'firstOrNew',
        'updateOrCreate', 'firstWhere', 'getById', 'getAll', 'getOne',

        # Query Builder
        'where', 'select', 'from', 'join', 'orderBy', 'groupBy', 'having',
        'limit', 'offset', 'take', 'skip', 'paginate', 'count', 'sum', 'avg',

        # Collection/Array Operations
        'map', 'filter', 'reduce', 'each', 'every', 'some', 'sort', 'reverse',
        'first', 'last', 'pluck', 'chunk', 'flatten', 'unique', 'merge',

        # CRUD
        'save', 'update', 'create', 'destroy', 'delete', 'remove', 'insert',
        'persist', 'flush', 'refresh', 'detach', 'attach', 'sync',

        # Service/Handler Pattern
        'execute', 'handle', 'process', 'run', 'perform', 'apply',
        'validate', 'transform', 'parse', 'serialize', 'deserialize',
        'render', 'build', 'make', 'resolve', 'bind',

        # Event/Observer
        'emit', 'on', 'off', 'trigger', 'listen', 'subscribe', 'publish',
        'notify', 'observe', 'dispatch', 'broadcast',

        # Logging/Debug
        'log', 'info', 'warn', 'error', 'debug', 'trace', 'dump',

        # Lifecycle
        'init', 'start', 'stop', 'boot', 'register', 'destroy', 'dispose',
        'mount', 'unmount', 'setup', 'teardown', 'configure',
    }

    def calculate(self, name: str, context: str, lang: str,
                  has_similar: bool, file_has_imports: bool) -> float:
        confidence = 1.0

        # 1. Externe Library wahrscheinlich?
        if name.lower() in self.COMMON_EXTERNAL_NAMES:
            confidence -= 0.3

        # 2. Datei hat viele Imports? → Externe Aufrufe wahrscheinlicher
        if file_has_imports:
            confidence -= 0.15

        # 3. Dynamische Patterns in der Datei?
        if self._has_dynamic_patterns(context, lang):
            confidence -= 0.25

        # 4. Ähnliches Symbol existiert? → Wahrscheinlich Tippfehler
        if has_similar:
            confidence += 0.1  # Eher ein echter Fehler

        # 5. Sehr kurzer Name? → Wahrscheinlich extern
        if len(name) <= 3:
            confidence -= 0.2

        return max(0.1, min(1.0, confidence))

    def _has_dynamic_patterns(self, content: str, lang: str) -> bool:
        patterns = DYNAMIC_PATTERNS.get(lang, [])
        for pattern in patterns:
            if re.search(pattern, content):
                return True
        return False
```

**Integration in handlers.py (finish):**

```python
@handler.register("chainguard_finish")
async def handle_finish(args: Dict[str, Any]) -> List[TextContent]:
    # ... existing code ...

    if state.mode == TaskMode.PROGRAMMING and config.SYMBOL_CHECK_ENABLED:
        validator = SymbolValidator(state.working_dir, state.session_defined_symbols)
        issues = validator.quality_check_with_confidence(list(state.changed_files))

        # Gruppiere nach Severity
        high = [i for i in issues if i.severity == "HIGH"]
        medium = [i for i in issues if i.severity == "MEDIUM"]
        low = [i for i in issues if i.severity == "LOW"]

        # Nur HIGH blockt, MEDIUM/LOW sind Warnings
        if high and not args.get("force"):
            response_parts.append(format_issues_by_severity(high, medium, low))
            response_parts.append("\n⚠️ HIGH confidence issues found. Fix or use force=True.")
            return [TextContent(type="text", text="\n".join(response_parts))]

        # MEDIUM/LOW nur als Info anzeigen
        if medium or low:
            response_parts.append(format_issues_by_severity([], medium, low))
```

**Output-Format:**

```
🔴 HIGH CONFIDENCE (likely real issues):
  • getUserById() in UserController.php:45 [0.92]
    → Did you mean: findUserById?

🟡 MEDIUM CONFIDENCE (review recommended):
  • sendMail() in NotificationService.php:67 [0.65]
    → Possibly external library method

🟢 LOW CONFIDENCE (likely OK):
  • request() in ApiClient.php:23 [0.35]
    → Common external method name
```

---

### 10.4 Token-Effiziente Architektur

#### Problem
```
Codebase: 5000 Dateien, 50.000 Symbole
Symbol-Tabelle als JSON: ~100.000 Tokens
→ UNBEZAHLBAR
```

#### Lösung: Multi-Layer Optimization

**1. Scope-Only Scanning (project_manager.py):**

```python
# project_manager.py

class ProjectManager:
    async def get_scope_files(self, state: ProjectState) -> List[Path]:
        """Gibt nur Dateien im definierten Scope zurück."""
        scope_files = []

        for pattern in state.modules:
            # Glob-Pattern auflösen
            matched = list(Path(state.working_dir).glob(pattern))
            scope_files.extend(matched)

        # Excludes anwenden
        return [f for f in scope_files if not self._should_exclude(f)]
```

**2. Inkrementeller Cache (cache.py erweitern):**

```python
# cache.py

class SymbolCache:
    """Persistenter Symbol-Cache mit File-Hashes."""

    def __init__(self, project_id: str):
        self.cache_file = CACHE_DIR / project_id / "symbol_cache.json"
        self.file_hashes: Dict[str, str] = {}
        self.file_symbols: Dict[str, List[dict]] = {}
        self._load()

    def _get_file_hash(self, file: Path) -> str:
        """Schneller Hash basierend auf mtime + size."""
        stat = file.stat()
        return f"{stat.st_mtime}:{stat.st_size}"

    def needs_rescan(self, file: Path) -> bool:
        """Prüft ob Datei neu gescannt werden muss."""
        key = str(file)
        current_hash = self._get_file_hash(file)
        return self.file_hashes.get(key) != current_hash

    def update(self, file: Path, symbols: List[dict]):
        """Aktualisiert Cache für eine Datei."""
        key = str(file)
        self.file_hashes[key] = self._get_file_hash(file)
        self.file_symbols[key] = symbols
        self._save_debounced()  # Nutzt bestehenden Debounce-Mechanismus

    def get_all_symbols(self) -> Dict[str, List[SymbolLocation]]:
        """Gibt alle gecachten Symbole zurück."""
        result = {}
        for file, symbols in self.file_symbols.items():
            for sym in symbols:
                result.setdefault(sym['name'], []).append(
                    SymbolLocation(file=file, line=sym['line'], symbol_type=sym['type'])
                )
        return result
```

**3. TOON-Format für Output (toon.py nutzen):**

```python
# symbol_validator.py

def format_report_toon(self, issues: List[SymbolIssue]) -> str:
    """Kompaktes TOON-Format für Token-Effizienz."""
    if not issues:
        return "✓ symbols:OK"

    # TOON-Array-Format
    from .toon import toon_array

    issue_data = [
        {
            'sym': i.name,
            'file': Path(i.file).name,  # Nur Filename, nicht voller Pfad
            'line': i.line,
            'conf': f"{i.confidence:.0%}",
            'fix': i.similar[0] if i.similar else '-'
        }
        for i in issues[:10]
    ]

    return toon_array(issue_data, "issues", fields=['sym', 'file', 'line', 'conf', 'fix'])

    # Output:
    # issues[3]{sym,file,line,conf,fix}:
    #   getUserById,UserCtrl.php,45,92%,findUserById
    #   sendMail,NotifSvc.php,67,65%,-
    #   request,ApiClient.php,23,35%,-
```

**Token-Vergleich:**

| Format | Tokens (10 Issues) |
|--------|-------------------|
| Verbose JSON | ~800 |
| Standard Text | ~400 |
| **TOON** | **~150** |

---

### 10.5 Progress-Anzeige (Streaming Output)

#### Problem
```
Großes Projekt: Scan dauert 30 Sekunden
User sieht nichts, denkt es hängt
```

#### Lösung: Async Generator mit Progress

**Neue Streaming-Architektur in handlers.py:**

```python
# handlers.py

@handler.register("chainguard_finish")
async def handle_finish(args: Dict[str, Any]) -> List[TextContent]:
    state = await get_current_state()
    response_parts = []

    # Symbol-Check mit Progress
    if state.mode == TaskMode.PROGRAMMING and config.SYMBOL_CHECK_ENABLED:
        response_parts.append("🔍 Symbol Validation\n")

        validator = SymbolValidator(state.working_dir, state.session_defined_symbols)
        scope_files = await project_manager.get_scope_files(state)
        total = len(scope_files)

        # Phase 1: Scanning mit Progress
        response_parts.append(f"   Scanning {total} files in scope...\n")

        scanned = 0
        for file in scope_files:
            scanned += 1

            # Progress alle 100 Files oder bei letzter Datei
            if scanned % 100 == 0 or scanned == total:
                pct = int((scanned / total) * 100)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                response_parts.append(f"   [{bar}] {pct}% ({scanned}/{total})\n")

            await validator.scan_file_async(file)

        response_parts.append(f"   ✓ Scanned {total} files\n\n")

        # Phase 2: Validation
        response_parts.append(f"   Validating {len(state.changed_files)} changed files...\n")

        issues = []
        for file in state.changed_files:
            file_issues = validator.validate_file(file)
            if file_issues:
                response_parts.append(f"   ⚠️ {Path(file).name}: {len(file_issues)} issues\n")
            issues.extend(file_issues)

        # Phase 3: Report
        response_parts.append(f"\n{'─'*50}\n")
        response_parts.append(validator.format_report(issues))
```

**Alternative: Background Task (für sehr große Projekte):**

```python
# Neues Tool: chainguard_symbol_scan_async

@handler.register("chainguard_symbol_scan")
async def handle_symbol_scan(args: Dict[str, Any]) -> List[TextContent]:
    """Startet Symbol-Scan als Background-Task."""
    background = args.get("background", False)

    if background:
        # Task starten und sofort zurückkehren
        task_id = await start_background_task(
            "symbol_scan",
            _run_symbol_scan,
            state.working_dir,
            state.changed_files
        )
        return [TextContent(
            type="text",
            text=f"🔄 Symbol scan started (task_id: {task_id})\n"
                 f"   Use chainguard_task_status(task_id='{task_id}') to check progress."
        )]
    else:
        # Synchron ausführen
        return await _run_symbol_scan(state.working_dir, state.changed_files)

@handler.register("chainguard_task_status")
async def handle_task_status(args: Dict[str, Any]) -> List[TextContent]:
    """Zeigt Status eines Background-Tasks."""
    task_id = args.get("task_id")
    task = get_background_task(task_id)

    if not task:
        return [TextContent(type="text", text=f"❌ Task {task_id} not found")]

    if task.status == "running":
        return [TextContent(
            type="text",
            text=f"🔄 Task {task_id}: {task.progress}\n"
                 f"   [{task.progress_bar}] {task.percent}%"
        )]
    elif task.status == "completed":
        return [TextContent(type="text", text=task.result)]
    else:
        return [TextContent(type="text", text=f"❌ Task failed: {task.error}")]
```

---

### 10.6 Automatisches Fixing durch LLM

#### Problem
```
Validator: "getUserById nicht gefunden"
LLM: "OK, ich habe verstanden" *macht nichts*
```

#### Lösung: Strukturierte Fix-Anweisungen

**Neues Ausgabe-Format:**

```python
# symbol_validator.py

def format_actionable_report(self, issues: List[SymbolIssue]) -> str:
    """Generiert LLM-freundliche Fix-Anweisungen."""

    if not issues:
        return "✓ All symbols verified"

    report = []
    report.append("⚠️ SYMBOL VALIDATION FAILED\n")
    report.append("="*60 + "\n\n")

    # Fix-Block der vom LLM verstanden wird
    report.append("## REQUIRED FIXES:\n\n")

    for i, issue in enumerate(issues, 1):
        if issue.confidence < 0.5:
            continue  # Nur HIGH confidence

        report.append(f"### Fix {i}: {issue.name}()\n\n")
        report.append(f"**Location:** `{issue.file}` line {issue.line}\n\n")

        if issue.similar:
            best = issue.similar[0]
            loc = issue.locations[0] if issue.locations else None

            report.append("**Action Required:**\n")
            report.append("```\n")
            report.append(f"1. Open file: {issue.file}\n")
            report.append(f"2. Go to line: {issue.line}\n")
            report.append(f"3. Replace: {issue.name}\n")
            report.append(f"4. With: {best}\n")
            if loc:
                report.append(f"5. Reference: {loc.file}:{loc.line}\n")
            report.append("```\n\n")

            # Expliziter Edit-Befehl für LLM
            report.append("**Suggested Edit Command:**\n")
            report.append(f"```python\n")
            report.append(f"Edit(\n")
            report.append(f"    file_path=\"{issue.file}\",\n")
            report.append(f"    old_string=\"{issue.name}(\",\n")
            report.append(f"    new_string=\"{best}(\"\n")
            report.append(f")\n")
            report.append("```\n\n")

        report.append("---\n\n")

    report.append("\n## NEXT STEPS:\n")
    report.append("1. Apply all fixes above using the Edit tool\n")
    report.append("2. Run `chainguard_track()` for each fixed file\n")
    report.append("3. Run `chainguard_finish()` again to verify\n")

    return ''.join(report)
```

**Optionales Auto-Fix Tool:**

```python
# tools.py - Neues Tool

SYMBOL_FIX_TOOL = {
    "name": "chainguard_symbol_fix",
    "description": "Automatically fix a hallucinated symbol by replacing it with the correct one.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "File containing the issue"},
            "old_symbol": {"type": "string", "description": "Wrong symbol name"},
            "new_symbol": {"type": "string", "description": "Correct symbol name"},
        },
        "required": ["file", "old_symbol", "new_symbol"]
    }
}

# handlers.py

@handler.register("chainguard_symbol_fix")
async def handle_symbol_fix(args: Dict[str, Any]) -> List[TextContent]:
    """Fixt ein halluziniertes Symbol automatisch."""
    file_path = args["file"]
    old_symbol = args["old_symbol"]
    new_symbol = args["new_symbol"]

    # Datei lesen
    content = Path(file_path).read_text(encoding='utf-8')

    # Alle Vorkommen ersetzen (nur Funktionsaufrufe, nicht Definitionen)
    # Pattern: old_symbol( aber nicht function old_symbol(
    pattern = rf'(?<!function\s)(?<!def\s)\b{re.escape(old_symbol)}\s*\('

    new_content = re.sub(pattern, f'{new_symbol}(', content)

    if content == new_content:
        return [TextContent(type="text", text=f"⚠️ No occurrences of {old_symbol}() found")]

    # Datei schreiben
    Path(file_path).write_text(new_content, encoding='utf-8')

    # Auto-Track
    state = await get_current_state()
    state.changed_files.add(file_path)

    count = content.count(old_symbol + '(') - new_content.count(old_symbol + '(')

    return [TextContent(
        type="text",
        text=f"✓ Fixed {count} occurrence(s) of {old_symbol}() → {new_symbol}()\n"
             f"   File: {file_path}\n"
             f"   Auto-tracked. Run chainguard_finish() to verify."
    )]
```

---

### 10.7 Dynamic-Pattern Detection

#### Problem
```php
$method = "get" . $field . "Value";
$this->$method();  // Dynamischer Aufruf - nicht erkennbar
```

#### Lösung: Pattern-Erkennung + Confidence-Reduktion

**Implementierung in symbol_validator.py:**

```python
# symbol_validator.py

DYNAMIC_PATTERNS = {
    'php': [
        r'\$\$\w+',                    # $$variable
        r'\$this\s*->\s*\$\w+',        # $this->$method
        r'call_user_func\s*\(',        # call_user_func(...)
        r'call_user_func_array\s*\(',  # call_user_func_array(...)
        r'\$\w+\s*\([^)]*\)',          # $variable()
        r'->\s*\{\s*\$',               # ->{"$var"}
    ],
    'python': [
        r'getattr\s*\(',               # getattr(obj, 'method')
        r'setattr\s*\(',               # setattr(obj, 'attr', val)
        r'exec\s*\(',                  # exec(code)
        r'eval\s*\(',                  # eval(expr)
        r'__getattr__',                # Magic method
        r'globals\s*\(\s*\)\s*\[',     # globals()['func']
    ],
    'javascript': [
        r'\[\s*\w+\s*\]\s*\(',         # obj[variable]()
        r'\[\s*[\'"`][^\]]+[\'"`]\s*\]\s*\(',  # obj['method']()
        r'eval\s*\(',                  # eval(code)
        r'new\s+Function\s*\(',        # new Function(...)
        r'Reflect\.\w+\s*\(',          # Reflect.get/apply/etc
    ],
    'csharp': [
        r'GetMethod\s*\(',             # Type.GetMethod("name")
        r'GetProperty\s*\(',           # Type.GetProperty("name")
        r'Invoke\s*\(',                # method.Invoke(...)
        r'DynamicInvoke\s*\(',         # delegate.DynamicInvoke(...)
        r'dynamic\s+\w+',              # dynamic keyword
    ],
}

class DynamicPatternDetector:
    """Erkennt dynamische Aufruf-Patterns."""

    def analyze_file(self, content: str, lang: str) -> Dict[str, Any]:
        """Analysiert Datei auf dynamische Patterns."""
        patterns = DYNAMIC_PATTERNS.get(lang, [])

        found_patterns = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                found_patterns.append({
                    'pattern': pattern,
                    'count': len(matches),
                    'examples': matches[:3]
                })

        return {
            'has_dynamic': len(found_patterns) > 0,
            'dynamic_count': sum(p['count'] for p in found_patterns),
            'patterns': found_patterns,
            'confidence_modifier': self._calculate_modifier(found_patterns)
        }

    def _calculate_modifier(self, patterns: List[dict]) -> float:
        """Berechnet Confidence-Modifier basierend auf dynamischen Patterns."""
        if not patterns:
            return 1.0  # Keine Reduktion

        total_count = sum(p['count'] for p in patterns)

        if total_count >= 10:
            return 0.3  # Starke Reduktion
        elif total_count >= 5:
            return 0.5
        elif total_count >= 2:
            return 0.7
        else:
            return 0.85
```

**Integration:**

```python
def validate_file(self, file_path: str) -> List[SymbolIssue]:
    content = Path(file_path).read_text()
    lang = self.detect_language(file_path)

    # Dynamic-Pattern-Analyse
    dynamic_info = self.dynamic_detector.analyze_file(content, lang)

    issues = []
    for name, line_no in calls:
        if name not in self.defined_symbols:
            issue = SymbolIssue(
                name=name,
                file=file_path,
                line=line_no,
                confidence=self._base_confidence(name, lang),
                # ... other fields
            )

            # Confidence reduzieren wenn dynamische Patterns vorhanden
            issue.confidence *= dynamic_info['confidence_modifier']

            if dynamic_info['has_dynamic']:
                issue.reason += f" (dynamic patterns detected: {dynamic_info['dynamic_count']})"

            issues.append(issue)

    return issues
```

---

### 10.8 Import-Tracking für externe Libraries

#### Problem
```php
use GuzzleHttp\Client;
$client->request('GET', $url);  // Validator: "request() nicht gefunden!"
```

#### Lösung: Import-Analyse + externe Library-Erkennung

**Neues Modul: import_analyzer.py**

```python
# import_analyzer.py

from dataclasses import dataclass
from typing import Dict, Set, List
import re

@dataclass
class ImportInfo:
    """Informationen über einen Import."""
    package: str           # Vollständiger Package-Name
    alias: str | None     # Alias falls vorhanden
    symbols: Set[str]     # Importierte Symbole (bei named imports)
    is_external: bool     # Vendor/node_modules?

class ImportAnalyzer:
    """Analysiert Import-Statements und erkennt externe Libraries."""

    KNOWN_EXTERNAL_PREFIXES = {
        'php': [
            'GuzzleHttp', 'Symfony', 'Illuminate', 'Laravel', 'Doctrine',
            'Carbon', 'Monolog', 'League', 'PHPUnit', 'Mockery',
            'Psr', 'Http', 'Aws', 'Google', 'Firebase',
        ],
        'javascript': [
            'react', 'vue', 'angular', 'express', 'axios', 'lodash',
            'moment', 'dayjs', 'jquery', 'bootstrap', 'tailwind',
            '@types', '@angular', '@nestjs', '@apollo', '@prisma',
        ],
        'csharp': [
            'Microsoft', 'System', 'Newtonsoft', 'AutoMapper', 'MediatR',
            'FluentValidation', 'Serilog', 'NLog', 'Dapper', 'EntityFramework',
            'Moq', 'NUnit', 'xUnit', 'Bogus', 'Polly',
        ],
        'python': [
            'django', 'flask', 'fastapi', 'requests', 'numpy', 'pandas',
            'sqlalchemy', 'pytest', 'celery', 'redis', 'boto3', 'httpx',
        ],
    }

    def extract_imports(self, content: str, lang: str) -> List[ImportInfo]:
        """Extrahiert alle Imports aus einer Datei."""
        imports = []

        if lang == 'php':
            imports = self._extract_php_imports(content)
        elif lang in ('javascript', 'typescript'):
            imports = self._extract_js_imports(content)
        elif lang == 'csharp':
            imports = self._extract_csharp_imports(content)
        elif lang == 'python':
            imports = self._extract_python_imports(content)

        # Externe Libraries markieren
        for imp in imports:
            imp.is_external = self._is_external(imp.package, lang)

        return imports

    def _extract_php_imports(self, content: str) -> List[ImportInfo]:
        imports = []

        # use Vendor\Package\Class;
        for match in re.finditer(r'use\s+([\w\\]+)(?:\s+as\s+(\w+))?;', content):
            imports.append(ImportInfo(
                package=match.group(1),
                alias=match.group(2),
                symbols=set(),
                is_external=False
            ))

        return imports

    def _extract_js_imports(self, content: str) -> List[ImportInfo]:
        imports = []

        # import { a, b } from 'package';
        for match in re.finditer(
            r'import\s*\{([^}]+)\}\s*from\s*[\'"]([^\'"]+)[\'"]',
            content
        ):
            symbols = {s.strip().split(' as ')[0] for s in match.group(1).split(',')}
            imports.append(ImportInfo(
                package=match.group(2),
                alias=None,
                symbols=symbols,
                is_external=False
            ))

        # import pkg from 'package';
        for match in re.finditer(
            r'import\s+(\w+)\s+from\s*[\'"]([^\'"]+)[\'"]',
            content
        ):
            imports.append(ImportInfo(
                package=match.group(2),
                alias=match.group(1),
                symbols=set(),
                is_external=False
            ))

        return imports

    def _is_external(self, package: str, lang: str) -> bool:
        """Prüft ob ein Package extern ist."""
        prefixes = self.KNOWN_EXTERNAL_PREFIXES.get(lang, [])

        for prefix in prefixes:
            if package.startswith(prefix) or prefix in package:
                return True

        # Heuristik: Vendor-Pfade
        if 'vendor' in package.lower() or 'node_modules' in package:
            return True

        return False

    def get_external_methods(self, imports: List[ImportInfo]) -> Set[str]:
        """Gibt alle Methoden zurück die wahrscheinlich extern sind."""
        external_symbols = set()

        for imp in imports:
            if imp.is_external:
                external_symbols.update(imp.symbols)
                # Füge auch den Alias hinzu (für Default-Imports)
                if imp.alias:
                    external_symbols.add(imp.alias)

        return external_symbols
```

**Integration in symbol_validator.py:**

```python
class SymbolValidator:
    def __init__(self, codebase_path: str, session_symbols: Set[str] = None):
        # ... existing init ...
        self.import_analyzer = ImportAnalyzer()

    def validate_file(self, file_path: str) -> List[SymbolIssue]:
        content = Path(file_path).read_text()
        lang = self.detect_language(file_path)

        # Import-Analyse
        imports = self.import_analyzer.extract_imports(content, lang)
        external_methods = self.import_analyzer.get_external_methods(imports)
        has_external_imports = any(i.is_external for i in imports)

        issues = []
        for name, line_no in calls:
            # Skip wenn wahrscheinlich externe Methode
            if name in external_methods:
                continue

            if name not in self.defined_symbols:
                issue = SymbolIssue(...)

                # Confidence reduzieren wenn externe Imports vorhanden
                if has_external_imports:
                    issue.confidence *= 0.85
                    issue.reason += " (file has external imports)"

                issues.append(issue)

        return issues
```

---

### 10.9 Performance-Optimierung für große Projekte

#### Problem
```
Enterprise Projekt: 50.000 Dateien
Full Scan: 5 Minuten → UNBENUTZBAR
```

#### Lösung: Multi-Layer Performance-Optimierung

**1. Parallel Scanning (symbol_validator.py):**

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AsyncSymbolValidator(SymbolValidator):
    """Symbol-Validator mit Parallel-Processing."""

    def __init__(self, codebase_path: str, session_symbols: Set[str] = None):
        super().__init__(codebase_path, session_symbols)
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def scan_codebase_async(self) -> int:
        """Scannt Codebase parallel."""
        if self._scanned:
            return len(self.defined_symbols)

        # Alle Dateien sammeln
        files_to_scan = []
        for ext, lang in self.LANGUAGE_MAP.items():
            for file in self.codebase_path.rglob(f"*{ext}"):
                if not self._should_skip_dir(file):
                    files_to_scan.append((file, lang))

        # Parallel scannen mit Semaphore
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent

        async def scan_with_limit(file: Path, lang: str):
            async with semaphore:
                return await self._scan_file_async(file, lang)

        tasks = [scan_with_limit(f, l) for f, l in files_to_scan]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Ergebnisse zusammenführen
        for result in results:
            if isinstance(result, dict):
                for name, locations in result.items():
                    self.defined_symbols.setdefault(name, []).extend(locations)

        self._scanned = True
        return len(self.defined_symbols)

    async def _scan_file_async(self, file: Path, lang: str) -> Dict[str, List]:
        """Scannt eine einzelne Datei async."""
        try:
            # I/O in Thread-Pool auslagern
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                self.executor,
                lambda: file.read_text(encoding='utf-8', errors='ignore')
            )

            definitions = self._extract_definitions(content, lang)

            result = {}
            rel_path = str(file.relative_to(self.codebase_path))

            for name, line_no, sym_type in definitions:
                location = SymbolLocation(rel_path, line_no, sym_type)
                result.setdefault(name, []).append(location)

            return result

        except Exception:
            return {}
```

**2. Scope-basierte Einschränkung (handlers.py):**

```python
@handler.register("chainguard_finish")
async def handle_finish(args: Dict[str, Any]) -> List[TextContent]:
    state = await get_current_state()

    if config.SYMBOL_CHECK_ENABLED:
        # NUR Scope-Module scannen, nicht ganze Codebase!
        validator = AsyncSymbolValidator(state.working_dir, state.session_symbols)

        # Scope-Patterns in Glob-Patterns umwandeln
        scope_files = []
        for pattern in state.modules:
            matched = list(Path(state.working_dir).glob(pattern))
            scope_files.extend(matched)

        # Nur diese Dateien scannen
        await validator.scan_files_async(scope_files)

        # Validierung nur für geänderte Dateien
        issues = validator.quality_check(list(state.changed_files))
```

**3. Depth-Limited Import Following:**

```python
class SymbolValidator:
    MAX_IMPORT_DEPTH = 2  # Nur 2 Ebenen tief folgen

    def _follow_imports(self, file: Path, depth: int = MAX_IMPORT_DEPTH) -> Set[str]:
        """Folgt Imports nur bis zu einer bestimmten Tiefe."""
        if depth <= 0:
            return set()

        content = file.read_text(encoding='utf-8')
        lang = self.detect_language(str(file))

        imports = self.import_analyzer.extract_imports(content, lang)
        symbols = set()

        for imp in imports:
            if not imp.is_external:
                # Interne Datei auflösen
                imp_file = self._resolve_import(imp.package, file.parent)
                if imp_file and imp_file.exists():
                    # Symbole aus importierter Datei extrahieren
                    defs = self._extract_definitions(
                        imp_file.read_text(),
                        self.detect_language(str(imp_file))
                    )
                    symbols.update(d[0] for d in defs)

                    # Rekursiv folgen (mit reduzierter Tiefe)
                    symbols.update(self._follow_imports(imp_file, depth - 1))

        return symbols
```

**Performance-Benchmarks (geschätzt):**

| Optimierung | Faktor |
|-------------|--------|
| Parallel I/O | 3-5x schneller |
| Scope-Only | 10-50x weniger Dateien |
| Caching | 90% schneller bei Re-Scan |
| Import-Depth-Limit | Verhindert Explosion |

**Gesamt:**

| Projekt-Größe | Ohne Optimierung | Mit Optimierung |
|---------------|------------------|-----------------|
| 100 Dateien | 2s | 0.3s |
| 1.000 Dateien | 15s | 1.5s |
| 10.000 Dateien | 120s | 5s |
| 50.000 Dateien | 600s | 20s |

---

### 10.10 Adaptive Modi (Balance Strikt/Locker)

#### Problem
```
Feature ist entweder:
- Zu strikt → User schaltet ab
- Zu locker → Bringt nichts
```

#### Lösung: Kontext-basierte adaptive Modi

**Neue Konfiguration in config.py:**

```python
# config.py

from enum import Enum

class SymbolValidationMode(Enum):
    OFF = "off"           # Deaktiviert
    WARN = "warn"         # Nur Warnings, kein Block
    STRICT = "strict"     # Blockt bei HIGH confidence
    ADAPTIVE = "adaptive" # Passt sich an Kontext an

# Default-Modus (v2.1: WARN statt ADAPTIVE!)
# WICHTIG: WARN zeigt Probleme, blockiert aber NIEMALS.
# STRICT nur wenn User explizit aktiviert (via chainguard_symbol_mode)
SYMBOL_VALIDATION_MODE = SymbolValidationMode.WARN

# File-Patterns für automatische Striktheit
SYMBOL_STRICT_PATTERNS = [
    r'Controller\.', r'Service\.', r'Repository\.',
    r'Api/', r'Handler\.', r'Middleware\.',
    r'UseCase\.', r'Command\.', r'Query\.',
]

SYMBOL_RELAXED_PATTERNS = [
    r'/test', r'/tests', r'Test\.', r'Spec\.',
    r'/config', r'/migrations', r'/seeds',
    r'\.config\.', r'\.env',
]
```

**Implementierung in symbol_validator.py:**

```python
class AdaptiveSymbolValidation:
    """Kontext-basierte Symbol-Validierung."""

    def get_mode_for_file(self, file: str, state: ProjectState) -> SymbolValidationMode:
        """Bestimmt den Validierungs-Modus basierend auf Kontext."""

        # 1. User-Override hat höchste Priorität
        if file in state.symbol_strict_files:
            return SymbolValidationMode.STRICT
        if file in state.symbol_ignore_files:
            return SymbolValidationMode.OFF

        # 2. Kritische Dateien → STRICT
        for pattern in config.SYMBOL_STRICT_PATTERNS:
            if re.search(pattern, file, re.IGNORECASE):
                return SymbolValidationMode.STRICT

        # 3. Test/Config → WARN only
        for pattern in config.SYMBOL_RELAXED_PATTERNS:
            if re.search(pattern, file, re.IGNORECASE):
                return SymbolValidationMode.WARN

        # 4. Default → ADAPTIVE (basierend auf Confidence)
        return SymbolValidationMode.ADAPTIVE

    def should_block(self, issues: List[SymbolIssue], mode: SymbolValidationMode) -> bool:
        """Entscheidet ob der Finish-Vorgang geblockt werden soll.

        WICHTIG (v2.1): False Positives dürfen NIEMALS den Workflow blockieren!
        - OFF, WARN, ADAPTIVE: Blockieren NIEMALS
        - STRICT: Blockiert nur bei sehr hoher Confidence (>0.9) UND vielen Issues (>=5)
        """

        # v2.1: Nur STRICT kann blockieren, alles andere zeigt nur Warnings
        if mode in (SymbolValidationMode.OFF,
                    SymbolValidationMode.WARN,
                    SymbolValidationMode.ADAPTIVE):
            return False  # NIEMALS blocken - nur Warnings anzeigen!

        if mode == SymbolValidationMode.STRICT:
            # v2.1: Höhere Schwellen um False Positives zu vermeiden
            # - Confidence muss >0.9 sein (vorher 0.8)
            # - Mindestens 5 Issues (vorher 3)
            # - User muss STRICT explizit aktiviert haben
            very_high = [i for i in issues if i.confidence > 0.9]
            return len(very_high) >= 5

        return False

    def get_effective_mode(self, files: List[str], state: ProjectState) -> SymbolValidationMode:
        """Bestimmt den effektiven Modus für eine Liste von Dateien.

        v2.1: NICHT mehr "strengster Modus gewinnt"!
        STRICT wird NUR verwendet wenn:
        1. User es explizit via chainguard_symbol_mode(mode="strict") aktiviert hat
        2. ALLE Dateien STRICT erfordern würden (nicht nur eine!)

        Begründung: Ein Controller in einer Session mit 10 Config-Dateien
        sollte nicht die gesamte Session auf STRICT setzen.
        """
        # v2.1: Prüfe ob User explizit STRICT aktiviert hat
        if hasattr(state, 'user_symbol_mode') and state.user_symbol_mode == SymbolValidationMode.STRICT:
            return SymbolValidationMode.STRICT

        modes = [self.get_mode_for_file(f, state) for f in files]

        # v2.1: WARN ist der sichere Default
        # STRICT nur wenn ALLE Dateien STRICT wären (sehr selten)
        if all(m == SymbolValidationMode.STRICT for m in modes) and modes:
            return SymbolValidationMode.STRICT

        # Sonst: Der mildeste aktive Modus
        if SymbolValidationMode.WARN in modes:
            return SymbolValidationMode.WARN
        if SymbolValidationMode.ADAPTIVE in modes:
            return SymbolValidationMode.ADAPTIVE  # Verhält sich wie WARN (kein Blocking)
        if SymbolValidationMode.OFF in modes:
            return SymbolValidationMode.OFF

        return SymbolValidationMode.WARN  # Safe default
```

**User-Feedback-System (Lernen aus Fehlern):**

```python
# models.py

@dataclass
class SymbolFeedback:
    """User-Feedback zu einem Symbol-Issue."""
    symbol: str
    file_pattern: str
    feedback: str  # "false_positive", "real_issue", "fixed"
    reason: str
    timestamp: datetime

# handlers.py

@handler.register("chainguard_symbol_feedback")
async def handle_symbol_feedback(args: Dict[str, Any]) -> List[TextContent]:
    """Speichert User-Feedback zu Symbol-Issues."""
    state = await get_current_state()

    feedback = SymbolFeedback(
        symbol=args["symbol"],
        file_pattern=args.get("file_pattern", "*"),
        feedback=args["feedback"],  # false_positive, real_issue, fixed
        reason=args.get("reason", ""),
        timestamp=datetime.now()
    )

    # Feedback speichern
    state.symbol_feedback.append(feedback)

    # Bei false_positive: Symbol zur Whitelist hinzufügen
    if feedback.feedback == "false_positive":
        state.symbol_whitelist.add(feedback.symbol)
        return [TextContent(
            type="text",
            text=f"✓ '{feedback.symbol}' added to whitelist.\n"
                 f"   Reason: {feedback.reason}\n"
                 f"   This symbol will be ignored in future validations."
        )]

    return [TextContent(type="text", text=f"✓ Feedback recorded for '{feedback.symbol}'")]
```

**Session Kill-Switch (NEU v2.1):**

```python
# handlers.py

@handler.register("chainguard_symbol_mode")
async def handle_symbol_mode(args: Dict[str, Any]) -> List[TextContent]:
    """Setzt Symbol-Validierungs-Modus für die aktuelle Session.

    WICHTIG: Erlaubt User, Validierung zu deaktivieren wenn sie stört.

    Args:
        mode: "off" | "warn" | "strict"
              - off: Komplett deaktiviert
              - warn: Zeigt Warnings, blockiert NIE (Default)
              - strict: Blockiert bei >0.9 Confidence + >=5 Issues

    Beispiele:
        chainguard_symbol_mode(mode="off")    # Komplett aus
        chainguard_symbol_mode(mode="warn")   # Nur Warnings (empfohlen)
        chainguard_symbol_mode(mode="strict") # Blockt echte Fehler
    """
    state = await get_current_state()
    mode_str = args.get("mode", "warn").lower()

    mode_map = {
        "off": SymbolValidationMode.OFF,
        "warn": SymbolValidationMode.WARN,
        "strict": SymbolValidationMode.STRICT,
    }

    if mode_str not in mode_map:
        return [TextContent(
            type="text",
            text=f"❌ Unknown mode '{mode_str}'. Use: off, warn, strict"
        )]

    state.user_symbol_mode = mode_map[mode_str]

    messages = {
        "off": "✓ Symbol validation: OFF (disabled for this session)",
        "warn": "✓ Symbol validation: WARN (shows issues, never blocks)",
        "strict": "✓ Symbol validation: STRICT (blocks on high-confidence issues)",
    }

    return [TextContent(type="text", text=messages[mode_str])]
```

**Tool-Definition (tools.py):**

```python
# tools.py

Tool(
    name="chainguard_symbol_mode",
    description="""Set symbol validation mode for current session.

Modes:
- off: Disable symbol validation completely
- warn: Show warnings but NEVER block (recommended, default)
- strict: Block on high-confidence issues (5+ issues with >90% confidence)

Use this if symbol validation is disrupting your workflow.""",
    inputSchema={
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["off", "warn", "strict"],
                "description": "Validation mode: off (disabled), warn (default), strict (blocking)",
                "default": "warn"
            }
        },
        "required": ["mode"]
    }
)
```

**Integration in handlers.py (finish):**

```python
@handler.register("chainguard_finish")
async def handle_finish(args: Dict[str, Any]) -> List[TextContent]:
    state = await get_current_state()

    if config.SYMBOL_CHECK_ENABLED and state.mode == TaskMode.PROGRAMMING:
        validator = AsyncSymbolValidator(state.working_dir, state.session_defined_symbols)
        adaptive = AdaptiveSymbolValidation()

        # Effektiven Modus bestimmen
        mode = adaptive.get_effective_mode(list(state.changed_files), state)

        if mode != SymbolValidationMode.OFF:
            # Validierung durchführen
            issues = await validator.quality_check_async(
                list(state.changed_files),
                whitelist=state.symbol_whitelist  # User-Whitelist anwenden
            )

            # Entscheiden ob blocken
            should_block = adaptive.should_block(issues, mode)

            if issues:
                response_parts.append(validator.format_report(issues, mode))

                if should_block and not args.get("force"):
                    response_parts.append(
                        f"\n⚠️ Symbol validation failed (mode: {mode.value}).\n"
                        f"   Fix issues or use force=True to complete.\n"
                        f"   Use chainguard_symbol_feedback() to report false positives."
                    )
                    return [TextContent(type="text", text="\n".join(response_parts))]
```

---

## 11. Architektur-Übersicht (v2.0)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SYMBOL VALIDATION SYSTEM v2.0                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │   models.py     │     │   config.py     │     │    cache.py     │       │
│  │                 │     │                 │     │                 │       │
│  │ • ProjectState  │     │ • SYMBOL_*      │     │ • SymbolCache   │       │
│  │   + session_    │     │   configs       │     │   + file_hashes │       │
│  │   symbols       │     │ • ValidationMode│     │   + TTL         │       │
│  │ • SymbolIssue   │     │ • Patterns      │     │                 │       │
│  │ • SymbolFeedback│     │                 │     │                 │       │
│  └────────┬────────┘     └────────┬────────┘     └────────┬────────┘       │
│           │                       │                       │                │
│           └───────────────────────┼───────────────────────┘                │
│                                   │                                        │
│                                   ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     symbol_validator.py                              │   │
│  │                                                                      │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │   │
│  │  │ AsyncSymbol      │  │ ConfidenceCalc   │  │ DynamicPattern   │   │   │
│  │  │ Validator        │  │                  │  │ Detector         │   │   │
│  │  │                  │  │ • calculate()    │  │                  │   │   │
│  │  │ • scan_async()   │  │ • modifiers      │  │ • analyze_file() │   │   │
│  │  │ • validate_file()│  │                  │  │ • patterns       │   │   │
│  │  │ • quality_check()│  │                  │  │                  │   │   │
│  │  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘   │   │
│  │           │                     │                     │              │   │
│  │           └─────────────────────┼─────────────────────┘              │   │
│  │                                 │                                    │   │
│  │  ┌──────────────────┐  ┌───────┴────────┐  ┌──────────────────┐     │   │
│  │  │ ImportAnalyzer   │  │ AdaptiveSymbol │  │ format_report()  │     │   │
│  │  │                  │  │ Validation     │  │                  │     │   │
│  │  │ • extract_imports│  │                │  │ • actionable     │     │   │
│  │  │ • is_external()  │  │ • get_mode()   │  │ • TOON format    │     │   │
│  │  │ • get_external() │  │ • should_block │  │ • by_severity    │     │   │
│  │  └──────────────────┘  └────────────────┘  └──────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                        │
│                                   ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        handlers.py                                   │   │
│  │                                                                      │   │
│  │  @handler.register("chainguard_track")                               │   │
│  │  → Extrahiert session_defined_symbols                                │   │
│  │                                                                      │   │
│  │  @handler.register("chainguard_finish")                              │   │
│  │  → Symbol-Validierung mit Progress                                   │   │
│  │  → Adaptive Mode Selection                                           │   │
│  │  → Actionable Fix-Anweisungen                                        │   │
│  │                                                                      │   │
│  │  @handler.register("chainguard_symbol_fix")                          │   │
│  │  → Automatisches Fixing                                              │   │
│  │                                                                      │   │
│  │  @handler.register("chainguard_symbol_feedback")                     │   │
│  │  → User-Feedback für Whitelist                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Neue Dateien (v2.0)

| Datei | Zweck | LOC (geschätzt) |
|-------|-------|-----------------|
| `symbol_validator.py` | Haupt-Validierungslogik | ~400 |
| `import_analyzer.py` | Import-Extraktion + externe Erkennung | ~200 |
| `symbol_patterns.py` | Alle Regex-Patterns | ~300 |
| `tests/test_symbol_validator.py` | Unit-Tests | ~500 |
| `tests/test_import_analyzer.py` | Import-Tests | ~200 |

**Geänderte Dateien:**

| Datei | Änderung |
|-------|----------|
| `models.py` | `session_defined_symbols`, `SymbolIssue`, `SymbolFeedback` |
| `handlers.py` | `handle_track`, `handle_finish`, neue Handler |
| `config.py` | `SYMBOL_*` Konfigurationen |
| `cache.py` | `SymbolCache` Klasse |
| `tools.py` | Neue Tool-Definitionen |

---

## 13. Implementierungs-Reihenfolge

### Phase 1: Core (MVP)
1. `symbol_patterns.py` - Alle Regex-Patterns
2. `symbol_validator.py` - Basis-Validierung
3. Integration in `handle_finish()`
4. Unit-Tests

### Phase 2: Robustheit
5. Session-Symbol-Tracking in `handle_track()`
6. Same-File Property Check
7. Confidence-Score System
8. Dynamic-Pattern Detection

### Phase 3: Performance
9. Async Scanning
10. Symbol-Cache
11. Scope-Only Scanning
12. TOON Output

### Phase 4: UX
13. Progress-Anzeige
14. Actionable Fix-Reports
15. `chainguard_symbol_fix` Tool
16. Adaptive Modi

### Phase 5: Learning
17. `chainguard_symbol_feedback`
18. User-Whitelist
19. Feedback-basierte Confidence-Anpassung

---

## 14. Zusammenfassung der Verbesserungen

| # | Verbesserung | Problem gelöst | Architektur-Impact |
|---|--------------|----------------|-------------------|
| 1 | Session-Aware Symbols | Neue Funktionen = False Positive | `models.py`, `handlers.py` |
| 2 | Same-File Check | Neue Properties = False Positive | `symbol_validator.py` |
| 3 | Confidence-Score | False Positives stören | `models.py`, `symbol_validator.py` |
| 4 | Token-Effizienz | Zu viele Tokens | `cache.py`, `toon.py` |
| 5 | Progress-Anzeige | UX bei langen Scans | `handlers.py` |
| 6 | Auto-Fix Anweisungen | LLM fixt nicht | `symbol_validator.py`, `handlers.py` |
| 7 | Dynamic-Pattern | Dynamische Sprachen | `symbol_validator.py` |
| 8 | Import-Tracking | Externe Libraries | `import_analyzer.py` |
| 9 | Performance | Große Projekte langsam | Async, Cache, Scope-Only |
| 10 | Adaptive Modi | Balance Strikt/Locker | `config.py`, `handlers.py` |

---

## 15. Changelog

### v2.1.0 (2026-01-09) - False-Positive-Safe Release

**⚠️ BREAKING CHANGE: Default-Mode geändert von ADAPTIVE auf WARN**

Diese Version stellt sicher, dass False Positives **niemals** den Workflow blockieren.

#### Geändert

| Änderung | Vorher | Nachher | Begründung |
|----------|--------|---------|------------|
| Default-Mode | `ADAPTIVE` | `WARN` | ADAPTIVE konnte blockieren |
| ADAPTIVE Blocking | Konnte blockieren | Blockiert NIE | False-Positive-Schutz |
| STRICT Confidence | `> 0.8` | `> 0.9` | Höhere Schwelle = weniger FP |
| STRICT Min. Issues | `>= 3` | `>= 5` | Mehr Issues nötig zum Blocken |
| "Strengster gewinnt" | Ja | Nein | Ein File sollte nicht alles STRICT machen |

#### Neu

- **`chainguard_symbol_mode` Tool**: Session Kill-Switch für Symbol-Validierung
  - `mode="off"`: Komplett deaktiviert
  - `mode="warn"`: Warnings ohne Blocking (Default)
  - `mode="strict"`: Blocking bei echten Fehlern (opt-in)

- **Erweiterte COMMON_EXTERNAL_NAMES**: ~80 Namen statt ~30
  - Repository Pattern: `findById`, `findAll`, `findOrFail`, etc.
  - Service Pattern: `execute`, `handle`, `process`, etc.
  - ORM: `persist`, `flush`, `refresh`, etc.

#### Philosophie v2.1

```
┌─────────────────────────────────────────────────────────────────┐
│                    FALSE POSITIVE HANDLING                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  v2.0 (ALT):                                                    │
│  ───────────                                                    │
│  "Zeige Fehler, blockiere bei vielen"                           │
│  → Problem: 3 False Positives = BLOCKIERT!                      │
│                                                                  │
│  v2.1 (NEU):                                                    │
│  ───────────                                                    │
│  "Zeige Warnings, blockiere NIE (außer User will es)"          │
│  → Lösung: Warnings informieren, User entscheidet               │
│                                                                  │
│  Prinzip: WARN > BLOCK                                          │
│  ─────────────────────────                                      │
│  - Lieber 10 Warnings zeigen als 1 False-Positive-Block        │
│  - User kann `force=True` nutzen, aber sollte nicht müssen     │
│  - STRICT nur wenn User es explizit aktiviert                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### v3.0.0 (2026-01-09) - Package Validation Release

**NEU: Slopsquatting-Detection für Package-Imports**

Forschung zeigt: ~20% der von LLMs empfohlenen Packages existieren nicht!

#### Neue Features

- **`chainguard_validate_packages` Tool**: Validiert Package-Imports gegen Registry
  - PHP: composer.json, composer.lock, vendor/
  - JS/TS: package.json, node_modules/
  - Python: requirements.txt, pyproject.toml, setup.py

- **Levenshtein Typo-Detection**: Findet ähnliche Packages
  - `lodas` → `lodash` (Slopsquatting-Warnung!)
  - `requsets` → `requests`

- **Standard-Library Whitelisting**:
  - Python: 150+ stdlib Module
  - Node.js: 50+ builtins (inkl. `node:` Prefix)
  - PHP: 60+ builtin Klassen

#### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `package_validator.py` | Hauptmodul für Package-Validierung |
| `test_package_validator.py` | 71 Unit-Tests |

#### Roadmap Completed

- [x] MVP: Symbol-Validierung
- [x] MVP: Package-Import Validierung (Slopsquatting)
- [x] 1100+ Unit-Tests

---

### v2.0.0 (2025-01-09) - Initial Extended Release

- Session-Aware Symbols
- Same-File Property Check
- Confidence-Score System
- Token-effiziente Architektur
- Progress-Anzeige
- Auto-Fix Anweisungen
- Dynamic-Pattern Detection
- Import-Tracking
- Performance-Optimierungen (Async, Cache)
- Adaptive Modi (WARN, STRICT, ADAPTIVE)
- User-Feedback-System

# Fix : Valeurs "nan" dans les cellules UD/FD/IDCC

## 🐛 Problème

Des valeurs "nan" (chaîne de caractères littérale) s'affichaient dans les cellules des colonnes UD (Union Départementale), FD (Fédération) et IDCC au lieu d'être affichées comme des cellules vides avec "—".

### Cause

Lors de l'import de fichiers Excel/CSV avec pandas, certaines cellules vides ou invalides peuvent être converties en la chaîne de caractères "nan" au lieu de la valeur Python `None`. Bien que le code d'import possède des mécanismes de nettoyage, il est possible que :
1. Certaines données aient été importées avant la mise en place de ces mécanismes
2. Des valeurs "nan" existent déjà dans la base de données
3. Le nettoyage n'ait pas été appliqué dans tous les cas

## ✅ Solution mise en place

La solution comprend **deux niveaux de protection** :

### 1. Nettoyage des données en base (Migration)

Un script de migration a été créé : `scripts/clean_nan_values.py`

Ce script :
- ✅ Nettoie toutes les valeurs "nan", "NaN", "NAN", "Nan" (insensible à la casse)
- ✅ Convertit ces valeurs en `NULL` dans la base de données
- ✅ S'applique à toutes les tables :
  - `Invitation` (colonnes : `fd`, `ud`, `idcc`)
  - `PVEvent` (colonnes : `FD`, `UD`, `idcc`)
  - `SiretSummary` (colonnes : `fd_c3`, `fd_c4`, `ud_c3`, `ud_c4`, `idcc`)

**Utilisation :**
```bash
python3 scripts/clean_nan_values.py
```

### 2. Filtre d'affichage (Templates Jinja2)

Un filtre Jinja2 personnalisé `clean_nan` a été ajouté dans `app/main.py` (lignes 312-323) :

```python
def clean_nan_filter(value):
    """Filtre Jinja2 pour convertir 'nan' en None ou valeur par défaut."""
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip().lower() in {'nan', 'none', 'null'}:
            return None
    return value
```

Ce filtre est appliqué dans tous les templates :
- ✅ `invitations.html` - Table des invitations
- ✅ `admin.html` - Page d'administration
- ✅ `calendrier.html` - Vue calendrier
- ✅ `siret.html` - Détail SIRET (Cycles 3 et 4)

**Exemples d'utilisation dans les templates :**
```jinja
{# Avant #}
{{ invit.fd or '—' }}

{# Après #}
{{ invit.fd | clean_nan or '—' }}
```

## 📊 Protection complète

Cette double approche garantit que :
1. **Les données existantes sont nettoyées** dans la base de données
2. **Les nouvelles données sont protégées** grâce au code d'import existant (`_clean_raw_value()` dans `app/etl.py`)
3. **L'affichage est sécurisé** même si une valeur "nan" passe à travers les filtres

## 🔄 Mécanismes de nettoyage existants

Le code possède déjà plusieurs niveaux de nettoyage lors de l'import :

### Dans `app/etl.py`

**Fonction `_clean_raw_value()` (lignes 23-35) :**
```python
def _clean_raw_value(value: Any) -> Any | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        lowered = cleaned.lower()
        if lowered in {"nan", "none", "null"}:  # ← Nettoyage des "nan"
            return None
        return cleaned
    return value
```

**Fonction `nan_to_none()` (lignes 775-781) :**
```python
def nan_to_none(val):
    try:
        if pd.isna(val):  # ← Détecte les NaN pandas
            return None
    except Exception:
        pass
    return val
```

Ces mécanismes sont utilisés :
- Lors de l'import d'invitations (`import_invitations_from_excel()`)
- Lors de la construction du résumé SIRET (`build_siret_summary()`)

## 🚀 Déploiement

Pour appliquer le fix sur un environnement :

1. **Déployer le code** avec les modifications
2. **Exécuter le nettoyage** (3 méthodes disponibles) :

### Méthode 1 : Interface Web (★ RECOMMANDÉ ★)

La méthode la plus simple ! Une fois l'application déployée :

1. Ouvrez votre navigateur
2. Accédez à : **`https://votre-domaine.com/admin/clean-nan`**
3. Cliquez sur le bouton "🚀 Lancer le nettoyage"
4. Les statistiques s'afficheront automatiquement

### Méthode 2 : Script Python

Si vous avez accès à un terminal avec la base de données :

```bash
python3 scripts/clean_nan_values.py
```

### Méthode 3 : API curl

Si vous préférez utiliser curl :

```bash
curl -X POST https://votre-domaine.com/admin/clean-nan/execute
```

3. **Vérifier le résultat** - Vous recevrez une réponse JSON avec les statistiques :
   ```json
   {
     "success": true,
     "message": "✅ Nettoyage terminé avec succès! 46 valeurs 'nan' nettoyées.",
     "total_cleaned": 46,
     "tables": {
       "Invitation": {
         "fd": 15,
         "ud": 23,
         "idcc": 8,
         "total": 46
       },
       "PVEvent": { ... },
       "SiretSummary": { ... }
     }
   }
   ```

4. **Redémarrer l'application** (les templates mis à jour seront automatiquement utilisés)

## 📝 Fichiers modifiés

| Fichier | Modification |
|---------|-------------|
| `scripts/clean_nan_values.py` | ✨ Nouveau - Script de migration CLI |
| `app/main.py` (lignes 18, 312-323) | ➕ Import `update`, filtre Jinja2 `clean_nan` |
| `app/main.py` (lignes 2776-3144) | ✨ Nouveaux endpoints API `/admin/clean-nan` |
| `app/templates/invitations.html` | 🔧 Utilisation du filtre pour FD, UD, IDCC |
| `app/templates/admin.html` | 🔧 Utilisation du filtre pour FD, UD |
| `app/templates/calendrier.html` | 🔧 Utilisation du filtre pour FD, UD, IDCC |
| `app/templates/siret.html` | 🔧 Utilisation du filtre pour FD, UD, IDCC (Cycles 3 et 4) |

### Nouveaux endpoints

- **`GET /admin/clean-nan`** : Interface web avec bouton pour lancer le nettoyage
- **`POST /admin/clean-nan/execute`** : Endpoint API qui exécute le nettoyage et retourne du JSON

## 🔍 Vérification

Après déploiement, vérifier que :
- [ ] Aucune cellule n'affiche "nan"
- [ ] Les cellules vides affichent "—" (tiret cadratin)
- [ ] Les valeurs valides (non-nan) s'affichent correctement
- [ ] Les filtres UD/FD dans la page invitations fonctionnent

## 📚 Références

- Code d'import : `app/etl.py`
- Modèles de données : `app/models.py`
- Documentation enrichissement FD : `ENRICHISSEMENT_FD_AUTOMATIQUE.md`

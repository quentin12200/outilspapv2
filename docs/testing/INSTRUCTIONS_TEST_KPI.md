# 🔧 Instructions pour tester les indicateurs KPI

## ⚡ Démarrage rapide

### Option 1 : Script automatique

```bash
./start_server_and_test.sh
```

Puis ouvrez http://localhost:8000/test-kpi dans votre navigateur.

### Option 2 : Démarrage manuel

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📍 Pages de test

Une fois le serveur démarré :

### 1. **Page de test dédiée** (RECOMMANDÉ)
http://localhost:8000/test-kpi

Cette page affiche :
- ✅ Status du chargement en temps réel
- 📊 Les KPIs dans des cartes visuelles
- 📝 La réponse JSON brute de l'API
- 📋 Les logs complets de chargement

**C'est la meilleure page pour diagnostiquer le problème !**

### 2. **Page d'accueil normale**
http://localhost:8000/

La page d'accueil avec Alpine.js. Si elle ne fonctionne pas, allez d'abord sur /test-kpi.

### 3. **API directe**
http://localhost:8000/api/stats/enriched

Retourne directement le JSON :
```json
{
  "total_invitations": 0,
  "audience_threshold": 1000,
  "pap_pv_overlap_percent": 0.0,
  "cgt_implanted_count": 0,
  "cgt_implanted_percent": 0.0,
  "elections_next_30_days": 0
}
```

---

## 🔍 Diagnostic selon ce que vous voyez

### ✅ Cas 1 : Sur /test-kpi tout est vert

**Symptôme** : La page /test-kpi affiche "✅ KPIs chargés avec succès"

**Mais les valeurs sont à 0**

→ **C'est NORMAL** si votre base de données est vide !

**Solutions** :
1. Allez sur http://localhost:8000/admin
2. Importez un fichier Excel d'invitations PAP
3. Retournez sur /test-kpi pour voir les vraies données

---

### ❌ Cas 2 : Sur /test-kpi j'ai une erreur rouge

**Symptôme** : Message "❌ Erreur: HTTP 404: Not Found" ou "Failed to fetch"

**Causes possibles** :

#### A. Le serveur n'est pas démarré
```bash
# Vérifiez si le serveur tourne
ps aux | grep uvicorn

# Si rien → démarrez-le
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### B. Le port est bloqué
```bash
# Vérifiez si le port 8000 est utilisé
lsof -i :8000

# Essayez un autre port
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
# Puis allez sur http://localhost:8080/test-kpi
```

#### C. Erreur 500 - Problème dans le code
Regardez les logs du serveur (terminal où vous avez lancé uvicorn).

Si vous voyez une erreur Python, copiez-la et envoyez-la.

---

### ❌ Cas 3 : La page d'accueil (/) ne fonctionne pas mais /test-kpi oui

**Symptôme** : /test-kpi fonctionne, mais la page d'accueil affiche toujours "—"

**Cause probable** : Problème avec Alpine.js ou le JavaScript

**Solution** :
1. Ouvrez la console du navigateur (F12)
2. Allez sur l'onglet "Console"
3. Cherchez des erreurs en rouge
4. Vous devriez voir :
   ```
   Chargement des KPIs depuis /api/stats/enriched...
   KPIs chargés: {données...}
   ```

Si vous ne voyez PAS ces messages :
- Alpine.js ne se charge peut-être pas
- Vérifiez votre connexion Internet (Alpine.js est chargé depuis un CDN)

---

## 📊 Exemple de réponse API normale

Si votre base de données contient des données, vous devriez voir quelque chose comme :

```json
{
  "total_invitations": 4523,
  "audience_threshold": 1000,
  "pap_pv_overlap_percent": 67.3,
  "cgt_implanted_count": 892,
  "cgt_implanted_percent": 45.2,
  "elections_next_30_days": 12
}
```

Si tout est à 0, c'est que la base de données est vide.

---

## 🐛 Que faire si ça ne fonctionne toujours pas ?

1. **Capturez ces informations** :
   - Allez sur http://localhost:8000/test-kpi
   - Faites une capture d'écran
   - Copiez le contenu de "Logs" et "Réponse API brute"

2. **Vérifiez les logs du serveur** :
   - Dans le terminal où vous avez lancé uvicorn
   - Copiez les dernières lignes (erreurs en rouge)

3. **Partagez ces informations** pour qu'on puisse vous aider

---

## ✅ Checklist de vérification

- [ ] Le serveur FastAPI est démarré (`python -m uvicorn app.main:app`)
- [ ] Le serveur tourne bien sur le port 8000
- [ ] http://localhost:8000/test-kpi est accessible
- [ ] La page /test-kpi affiche le status (même si erreur)
- [ ] J'ai vérifié la console du navigateur (F12)
- [ ] J'ai vérifié les logs du serveur (terminal)

---

## 📞 Pour aller plus loin

Si /test-kpi fonctionne et affiche des données :
→ Le problème n'est PAS l'API mais l'affichage sur la page d'accueil

Si /test-kpi ne fonctionne pas :
→ Le problème est au niveau du serveur ou de l'endpoint API

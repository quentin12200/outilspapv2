# Espace Utilisateur Personnel - Conformité RGPD

## 📋 Vue d'ensemble

L'espace utilisateur personnel permet à chaque utilisateur de consulter et modifier ses informations personnelles, conformément aux exigences du RGPD (Règlement Général sur la Protection des Données).

## 🎯 Objectifs

### Conformité RGPD

Cette fonctionnalité répond aux articles suivants du RGPD :

- **Article 15** : Droit d'accès aux données personnelles
- **Article 16** : Droit de rectification des données
- **Article 5** : Principe de transparence dans le traitement des données

## 📄 Fonctionnalités

### 1. Consultation du Profil

Route : `GET /profile`

Affiche toutes les informations personnelles de l'utilisateur :

#### Informations personnelles
- Prénom
- Nom
- Email (non modifiable directement)
- Téléphone

#### Informations syndicales
- Organisation
- Fédération (FD)
- Union Départementale (UD)
- Région
- Responsabilité

#### Informations du compte
- Statut du compte (Approuvé / En attente)
- Rôle (Utilisateur / Administrateur)
- Date de création du compte
- Dernière connexion
- Lien pour changer le mot de passe

### 2. Modification du Profil

Route : `POST /profile`

Permet à l'utilisateur de modifier ses informations personnelles.

#### Champs modifiables
- ✅ Prénom (requis)
- ✅ Nom (requis)
- ✅ Téléphone (optionnel)
- ✅ Organisation (requis)
- ✅ Fédération (optionnel)
- ✅ Union Départementale (optionnel)
- ✅ Région (optionnel)
- ✅ Responsabilité (optionnel)

#### Champs NON modifiables par l'utilisateur
- ❌ Email (nécessite validation admin pour éviter les abus)
- ❌ Rôle (seulement modifiable par admin)
- ❌ Statut d'approbation (seulement modifiable par admin)
- ❌ Statut actif (seulement modifiable par admin)
- ❌ Dates (created_at, updated_at, last_login)

### 3. Changement de Mot de Passe

Lien vers `/forgot-password` pour initier un processus de réinitialisation sécurisé.

## 🔒 Sécurité

### Protection de la Route

La route `/profile` est protégée par l'authentification utilisateur :

```python
@app.get("/profile", response_class=HTMLResponse)
def user_profile_page(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)  # Protection
):
```

L'utilisateur doit être connecté pour accéder à son profil.

### Validation des Données

Lors de la mise à jour du profil :

1. **Validation des champs requis** : Prénom, Nom, Organisation
2. **Nettoyage des données** : `.strip()` sur tous les champs
3. **Gestion des erreurs** : Rollback en cas d'erreur
4. **Logging** : Enregistrement des modifications

```python
# Validation des champs requis
if not first_name or not first_name.strip():
    raise ValueError("Le prénom est requis")
if not last_name or not last_name.strip():
    raise ValueError("Le nom est requis")
if not organization or not organization.strip():
    raise ValueError("L'organisation est requise")

# Mise à jour avec nettoyage
current_user.first_name = first_name.strip()
current_user.last_name = last_name.strip()
# ...
```

### Isolation des Données

Chaque utilisateur ne peut voir et modifier **uniquement ses propres données**. Le système utilise `current_user` (récupéré via le cookie de session) pour s'assurer que l'utilisateur ne peut pas accéder aux données d'un autre utilisateur.

## 🎨 Interface Utilisateur

### Navigation

Le lien "Mon profil" est accessible depuis :

#### Menu Desktop
- Menu déroulant utilisateur (en haut à droite)
- Clic sur le nom de l'utilisateur

#### Menu Mobile
- Menu hamburger
- Section profil utilisateur

### Design

- **TailwindCSS** : Design moderne et responsive
- **Sections organisées** : Informations personnelles, syndicales, compte
- **Messages de feedback** : Success/Error après modification
- **Champs clairement marqués** : Requis vs optionnels
- **Information visuelle** : Badge de statut, icônes

### Notice RGPD

Une notice explicative est affichée en bas de la page :

> "Conformément au RGPD, vous disposez d'un droit d'accès, de rectification et de suppression de vos données personnelles. Pour exercer ces droits ou pour toute question concernant vos données, contactez un administrateur."

## 📊 Traçabilité

### Logs

Chaque modification de profil est enregistrée dans les logs :

```python
logging.info(f"Profil mis à jour pour l'utilisateur {current_user.email}")
```

### Horodatage

Le champ `updated_at` est automatiquement mis à jour lors de chaque modification :

```python
current_user.updated_at = datetime.now()
db.commit()
```

## 🧪 Tests à Effectuer

### Test 1 : Accès au Profil
1. Se connecter en tant qu'utilisateur
2. Cliquer sur le menu utilisateur (desktop ou mobile)
3. Cliquer sur "Mon profil"
4. ✅ Vérifier que toutes les informations sont affichées correctement

### Test 2 : Modification des Informations
1. Accéder au profil
2. Modifier le prénom, nom, téléphone
3. Modifier organisation, FD, UD, région, responsabilité
4. Cliquer sur "Enregistrer les modifications"
5. ✅ Vérifier le message de succès
6. ✅ Vérifier que les modifications sont persistées

### Test 3 : Validation des Champs Requis
1. Accéder au profil
2. Vider le champ "Prénom"
3. Cliquer sur "Enregistrer les modifications"
4. ✅ Vérifier le message d'erreur "Le prénom est requis"

### Test 4 : Email Non Modifiable
1. Accéder au profil
2. ✅ Vérifier que le champ email est désactivé (grisé)
3. ✅ Vérifier la note explicative sous le champ

### Test 5 : Responsive Design
1. Tester sur desktop (> 768px)
2. Tester sur mobile (< 768px)
3. ✅ Vérifier que le layout s'adapte correctement

### Test 6 : Sécurité
1. Se déconnecter
2. Essayer d'accéder à `/profile` directement
3. ✅ Vérifier la redirection vers `/login`

## 📝 Code Source

### Fichiers Créés/Modifiés

| Fichier | Type | Description |
|---------|------|-------------|
| `app/templates/user_profile.html` | Template | Page de profil utilisateur |
| `app/main.py` | Routes | GET /profile et POST /profile |
| `app/templates/base.html` | Navigation | Lien "Mon profil" (desktop + mobile) |

### Routes

```python
# GET /profile - Afficher le profil
@app.get("/profile", response_class=HTMLResponse)
def user_profile_page(...)

# POST /profile - Mettre à jour le profil
@app.post("/profile", response_class=HTMLResponse)
def user_profile_post(...)
```

## 🔄 Workflow

```
┌─────────────────┐
│  Utilisateur    │
│   connecté      │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│  Menu utilisateur   │
│  "Mon profil"       │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  GET /profile       │
│  Affiche le profil  │
└────────┬────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Formulaire avec toutes     │
│  les informations           │
│  (certaines modifiables)    │
└────────┬────────────────────┘
         │
         │ Modification
         ▼
┌─────────────────────┐
│  POST /profile      │
│  Validation +       │
│  Enregistrement     │
└────────┬────────────┘
         │
         ├─── ✅ Succès ──→ Message "Mis à jour avec succès"
         │
         └─── ❌ Erreur ──→ Message d'erreur explicite
```

## 🌟 Avantages

### Pour l'Utilisateur
- ✅ Contrôle total sur ses données personnelles
- ✅ Mise à jour facile et rapide
- ✅ Transparence sur les informations collectées
- ✅ Interface intuitive et accessible

### Pour l'Organisation
- ✅ Conformité RGPD automatique
- ✅ Réduction des demandes de modification aux admins
- ✅ Données toujours à jour
- ✅ Traçabilité des modifications

### Pour la Sécurité
- ✅ Email non modifiable (évite l'usurpation)
- ✅ Rôle non modifiable (évite l'escalade de privilèges)
- ✅ Validation des données entrées
- ✅ Logging des modifications

## 📚 Références RGPD

### Articles Applicables

**Article 5 - Principes relatifs au traitement des données**
- Transparence : L'utilisateur voit toutes ses données
- Minimisation : Seules les données nécessaires sont collectées

**Article 15 - Droit d'accès**
- L'utilisateur peut consulter ses données personnelles

**Article 16 - Droit de rectification**
- L'utilisateur peut corriger ses données inexactes ou incomplètes

**Article 17 - Droit à l'effacement**
- Notice indiquant comment contacter un admin pour supprimer le compte

### Prochaines Étapes RGPD (Optionnel)

Pour une conformité encore plus complète :

1. **Export des données** : Permettre à l'utilisateur de télécharger toutes ses données (JSON/PDF)
2. **Suppression du compte** : Formulaire de demande de suppression
3. **Historique des modifications** : Journal des changements apportés au profil
4. **Consentement explicite** : Gestion des consentements (newsletters, etc.)
5. **Durée de conservation** : Afficher depuis combien de temps les données sont conservées

## ✅ Checklist de Déploiement

Avant le déploiement en production :

- [x] Template user_profile.html créé
- [x] Routes GET /profile et POST /profile ajoutées
- [x] Lien "Mon profil" ajouté dans la navigation (desktop + mobile)
- [x] Validation des champs requis implémentée
- [x] Messages de feedback (success/error) implémentés
- [x] Logging des modifications activé
- [x] Protection par authentification
- [x] Champs sensibles non modifiables (email, role)
- [x] Notice RGPD affichée
- [ ] Tests manuels effectués
- [ ] Tests sur différents navigateurs
- [ ] Tests responsive (mobile/tablet/desktop)
- [ ] Vérification des logs
- [ ] Documentation utilisateur (si nécessaire)

## 🎉 Résultat

Les utilisateurs disposent maintenant d'un espace personnel complet et conforme au RGPD pour gérer leurs informations personnelles de manière autonome et sécurisée.

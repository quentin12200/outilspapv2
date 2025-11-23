"""
Service de chatbot IA pour répondre à des questions sur les données PAP/CSE.

Ce service utilise GPT-4 pour interpréter des requêtes en langage naturel,
générer des requêtes SQL appropriées et retourner des réponses formatées.
"""

import logging
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

from openai import OpenAI
from ..config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MODEL_FALLBACK

logger = logging.getLogger(__name__)

# Chemin vers le dossier des argumentaires
ARGUMENTAIRES_DIR = Path(__file__).parent.parent / "data" / "argumentaires"


class ChatbotIA:
    """
    Chatbot IA pour interroger la base de données PAP/CSE en langage naturel.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le chatbot IA.

        Args:
            api_key: Clé API OpenAI. Si None, utilise OPENAI_API_KEY de la config.

        Raises:
            ValueError: Si la clé API n'est pas configurée.
        """
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise ValueError(
                "Clé API OpenAI manquante. "
                "Veuillez configurer OPENAI_API_KEY dans le fichier .env"
            )

        self.client = OpenAI(api_key=self.api_key)
        self.model = OPENAI_MODEL or "gpt-4o"

    def _call_openai_with_fallback(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Appelle l'API OpenAI avec mécanisme de fallback sur plusieurs modèles.

        Args:
            messages: Liste des messages pour l'API
            temperature: Température pour la génération
            response_format: Format de réponse (ex: {"type": "json_object"})

        Returns:
            Contenu de la réponse

        Raises:
            Exception: Si aucun modèle n'est accessible
        """
        last_error = None

        for attempt_model in OPENAI_MODEL_FALLBACK:
            try:
                logger.info(f"Tentative d'appel OpenAI avec le modèle: {attempt_model}")

                kwargs = {
                    "model": attempt_model,
                    "messages": messages,
                    "temperature": temperature
                }

                if response_format:
                    kwargs["response_format"] = response_format

                response = self.client.chat.completions.create(**kwargs)

                # Si on arrive ici, ça a marché !
                logger.info(f"✅ Appel réussi avec le modèle: {attempt_model}")
                return response.choices[0].message.content

            except Exception as e:
                error_msg = str(e)
                last_error = e

                # Si c'est une erreur d'accès au modèle, essayer le suivant
                if "does not have access" in error_msg or "model_not_found" in error_msg:
                    logger.warning(f"⚠️ Modèle {attempt_model} non accessible, essai du suivant...")
                    continue
                else:
                    # Autre type d'erreur, on arrête les tentatives
                    raise e

        # Aucun modèle n'a fonctionné
        raise Exception(
            f"Aucun modèle GPT accessible. Dernière erreur: {str(last_error)}. "
            f"Vérifiez que vous avez activé au moins un modèle GPT-4 dans votre projet OpenAI."
        )

    def _get_schema_info(self) -> str:
        """
        Retourne une description du schéma de la base de données.

        Returns:
            Description textuelle du schéma pour le contexte GPT.
        """
        return """
## Schéma de la base de données PAP/CSE

### Table: invitations
Table des invitations PAP (Protocole d'Accord Préélectoral) Cycle 5.
Colonnes:
- id (INTEGER): Identifiant unique
- siret (TEXT): Numéro SIRET de l'établissement (14 chiffres)
- date_invit (DATE): Date de l'invitation au PAP
- date_reception (DATE): Date de réception de l'invitation
- date_election (DATE): Date prévue de l'élection
- source (TEXT): Source de l'invitation (ex: "Scan automatique", "Import Manuel", "Email")
- ud (TEXT): Union Départementale (ex: "UD 75", "UD 13")
- fd (TEXT): Fédération (ex: "Métallurgie", "Chimie", "Commerce")
- idcc (TEXT): Code IDCC de la convention collective
- effectif_connu (INTEGER): Effectif de l'entreprise si connu
- structure_saisie (TEXT): Structure qui a saisi l'invitation
- created_at (DATETIME): Date de création dans la BDD
- updated_at (DATETIME): Date de dernière mise à jour
- raw (JSON): Données brutes complètes

Informations importantes:
- Les invitations peuvent être marquées avec différents statuts basés sur les dates
- La source "Scan automatique" indique une extraction automatique depuis un document scanné
- L'IDCC permet d'identifier la convention collective

### Table: Tous_PV
Table historique des PV (Procès-Verbaux) d'élections professionnelles.
Colonnes principales:
- siret (TEXT): Numéro SIRET de l'établissement
- raison_sociale (TEXT): Nom de l'entreprise
- effectif (INTEGER): Effectif de l'établissement
- date_scrutin (DATE): Date du scrutin
- date_prochain_scrutin (DATE): Date du prochain scrutin prévu
- cycle (TEXT): Cycle électoral (ex: "C5", "C4")
- institution (TEXT): Type d'institution (ex: "CSE", "CE", "DP", "CAR" pour carence)
- fd (TEXT): Fédération
- ud (TEXT): Union Départementale
- idcc (TEXT): Code IDCC
- region (TEXT): Région
- departement (TEXT): Département
- ville (TEXT): Ville
- code_postal (TEXT): Code postal
- participation_pourcent (REAL): Taux de participation en %
- sve (BOOLEAN): Syndicat Voix Electeur (1 = oui, 0 = non)

Informations sur les résultats électoraux:
- total_exprimes: Total des votes exprimés
- total_votants: Total des votants
- cgt_*: Résultats CGT (sièges, voix, %)
- cfdt_*: Résultats CFDT
- fo_*: Résultats FO
- cfe_cgc_*: Résultats CFE-CGC
- cftc_*: Résultats CFTC
- unsa_*: Résultats UNSA
- fsu_*: Résultats FSU
- solidaires_*: Résultats Solidaires
- autres_*: Autres syndicats

### Requêtes courantes:

**Compter les invitations:**
SELECT COUNT(*) FROM invitations

**Invitations par département (via UD):**
SELECT ud, COUNT(*) as count FROM invitations WHERE ud IS NOT NULL GROUP BY ud ORDER BY count DESC

**Invitations en retard (>60 jours sans date d'élection):**
SELECT COUNT(*) FROM invitations
WHERE date_election IS NULL
AND date_invit < date('now', '-60 days')

**Statistiques par source:**
SELECT source, COUNT(*) as count FROM invitations GROUP BY source

**Prochaines élections:**
SELECT COUNT(*) FROM Tous_PV
WHERE date_prochain_scrutin >= date('now')
AND date_prochain_scrutin <= date('now', '+30 days')

**Top FD par nombre de PV:**
SELECT fd, COUNT(*) as count FROM Tous_PV WHERE fd IS NOT NULL GROUP BY fd ORDER BY count DESC LIMIT 10
"""

    def _generate_sql_query(self, question: str, db: Session) -> Dict[str, Any]:
        """
        Génère une requête SQL à partir d'une question en langage naturel.

        Args:
            question: Question de l'utilisateur en langage naturel
            db: Session de base de données

        Returns:
            Dict avec la requête SQL, son explication et le type de réponse
        """
        schema = self._get_schema_info()

        prompt = f"""Tu es un assistant SQL expert pour une plateforme de gestion PAP/CSE (élections professionnelles).

{schema}

Question de l'utilisateur: {question}

IMPORTANT:
- Génère UNIQUEMENT une requête SQL SQLite sécurisée (pas d'UPDATE, DELETE, DROP)
- La requête doit être optimisée et pertinente
- Utilise des fonctions SQL appropriées (COUNT, SUM, GROUP BY, etc.)
- Pour les dates, utilise la fonction date() de SQLite
- Pour "aujourd'hui", utilise date('now')
- Les dates sont au format YYYY-MM-DD
- Retourne UNIQUEMENT un objet JSON avec cette structure:

{{
    "sql": "SELECT ...",
    "explanation": "Explication courte de ce que fait la requête",
    "response_type": "count|list|table|stat",
    "limit": 10
}}

Types de response_type:
- count: Une seule valeur numérique
- list: Liste d'éléments
- table: Tableau de données
- stat: Statistiques agrégées

Exemples:

Q: "Combien d'invitations en retard dans le 75 ?"
R: {{
    "sql": "SELECT COUNT(*) as count FROM invitations WHERE ud = 'UD 75' AND date_election IS NULL AND date_invit < date('now', '-60 days')",
    "explanation": "Compte les invitations du département 75 sans date d'élection et datant de plus de 60 jours",
    "response_type": "count",
    "limit": null
}}

Q: "Quelles entreprises ont une élection ce mois-ci ?"
R: {{
    "sql": "SELECT DISTINCT siret, raison_sociale, date_prochain_scrutin FROM Tous_PV WHERE date_prochain_scrutin >= date('now', 'start of month') AND date_prochain_scrutin < date('now', '+1 month', 'start of month') ORDER BY date_prochain_scrutin LIMIT 20",
    "explanation": "Liste les entreprises avec une élection prévue ce mois",
    "response_type": "table",
    "limit": 20
}}

Q: "Statistiques des invitations par source"
R: {{
    "sql": "SELECT source, COUNT(*) as count, ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM invitations), 2) as percentage FROM invitations GROUP BY source ORDER BY count DESC",
    "explanation": "Agrège les invitations par source avec pourcentages",
    "response_type": "stat",
    "limit": null
}}

Maintenant, génère la requête SQL pour la question de l'utilisateur.
"""

        try:
            content = self._call_openai_with_fallback(
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un expert SQL pour bases de données SQLite. Tu génères des requêtes SQL sécurisées et optimisées."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(content)
            logger.info(f"Requête SQL générée: {result.get('sql')}")
            return result

        except Exception as e:
            logger.error(f"Erreur lors de la génération SQL: {str(e)}")
            raise

    def _execute_query(self, sql: str, db: Session) -> List[Dict[str, Any]]:
        """
        Exécute une requête SQL de manière sécurisée.

        Args:
            sql: Requête SQL à exécuter
            db: Session de base de données

        Returns:
            Liste de résultats sous forme de dictionnaires

        Raises:
            ValueError: Si la requête contient des opérations dangereuses
        """
        # Vérification de sécurité
        sql_upper = sql.upper()
        dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE"]
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                raise ValueError(f"Requête non autorisée: contient '{keyword}'")

        try:
            result = db.execute(text(sql))

            # Convertir les résultats en liste de dictionnaires
            rows = []
            for row in result:
                # row est un objet Row qui se comporte comme un tuple et un dict
                row_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(zip(result.keys(), row))
                rows.append(row_dict)

            logger.info(f"Requête exécutée avec succès: {len(rows)} résultats")
            return rows

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution SQL: {str(e)}")
            raise

    def _format_response(
        self,
        question: str,
        sql_info: Dict[str, Any],
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Formate les résultats en réponse en langage naturel.

        Args:
            question: Question originale
            sql_info: Informations sur la requête SQL
            results: Résultats de la requête

        Returns:
            Réponse formatée en langage naturel
        """
        response_type = sql_info.get("response_type", "table")

        # Si pas de résultats
        if not results:
            return "Aucun résultat trouvé pour cette requête."

        prompt = f"""Tu es un assistant pour une plateforme PAP/CSE.

Question: {question}

Requête SQL: {sql_info.get('sql')}

Résultats:
{json.dumps(results, indent=2, default=str)}

INSTRUCTIONS:
- Réponds à la question de manière claire et professionnelle
- Utilise des formats adaptés (listes, tableaux, statistiques)
- Si c'est un nombre, indique-le clairement
- Si c'est une liste, présente-la de manière structurée
- Ajoute du contexte si pertinent
- Utilise des émojis appropriés (📊 pour stats, 🏢 pour entreprises, 📅 pour dates, etc.)

Exemples de formats:

Pour un compte:
"Il y a **23 invitations** en retard dans le département 75 (Paris) 🔴"

Pour une liste:
"Voici les 5 prochaines élections :
1. **ABC Corp** (SIRET: xxx) - 15/03/2024
2. **DEF SA** (SIRET: yyy) - 22/03/2024
..."

Pour des statistiques:
"📊 **Répartition des invitations par source** :
- Scan automatique: 145 (45%)
- Import Manuel: 102 (32%)
- Email: 73 (23%)"

Maintenant, réponds à la question de l'utilisateur.
"""

        try:
            content = self._call_openai_with_fallback(
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un assistant professionnel qui aide à interpréter des données sur les élections professionnelles."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3
            )

            return content

        except Exception as e:
            logger.error(f"Erreur lors du formatage de la réponse: {str(e)}")
            # Fallback: retourner les résultats bruts
            return f"Résultats trouvés: {len(results)} entrée(s)\n\n{json.dumps(results[:10], indent=2, default=str)}"

    def _load_argumentaires(self) -> Dict[str, Any]:
        """
        Charge les argumentaires depuis les fichiers JSON.

        Returns:
            Dictionnaire contenant tous les argumentaires chargés
        """
        argumentaires = {}

        try:
            # Charger le fichier de syndicalisation
            syndi_path = ARGUMENTAIRES_DIR / "syndicalisation_freins_leviers.json"
            if syndi_path.exists():
                with open(syndi_path, 'r', encoding='utf-8') as f:
                    argumentaires['syndicalisation'] = json.load(f)
                    logger.info("Argumentaires de syndicalisation chargés avec succès")
            else:
                logger.warning(f"Fichier d'argumentaires non trouvé: {syndi_path}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des argumentaires: {str(e)}")

        return argumentaires

    def _detect_question_type(self, question: str) -> str:
        """
        Détecte si la question porte sur les données (SQL) ou les argumentaires.

        Args:
            question: Question de l'utilisateur

        Returns:
            "sql" ou "argumentaire"
        """
        question_lower = question.lower()

        # Mots-clés indiquant une question sur les argumentaires
        argumentaire_keywords = [
            "freins", "syndicalisation", "adhésion", "adhérent", "syndiqué",
            "répression", "peur", "représailles", "qvs", "qualité de vie syndicale",
            "formation", "démocratie", "congrès", "ictam", "cadres", "tpe", "pme",
            "retraité", "continuité syndicale", "panier percé", "culture d'orga",
            "isolement", "institutionnalisation", "droits syndicaux", "cotisation",
            "leviers", "moyens", "stratégie", "renforcement", "structuration",
            "argumentaire", "comment convaincre", "comment expliquer", "pourquoi"
        ]

        # Mots-clés indiquant une question sur les données
        sql_keywords = [
            "combien", "nombre", "statistique", "invitations", "pap", "pv",
            "élection", "scrutin", "siret", "entreprise", "département", "ud", "fd",
            "fédération", "liste", "quelles", "quels", "où", "region", "effectif",
            "top", "classement", "taux", "participation", "résultat", "cgt", "cfdt"
        ]

        # Compter les correspondances
        argumentaire_score = sum(1 for kw in argumentaire_keywords if kw in question_lower)
        sql_score = sum(1 for kw in sql_keywords if kw in question_lower)

        logger.info(f"Scores de détection - SQL: {sql_score}, Argumentaire: {argumentaire_score}")

        # Si score égal, privilégier les argumentaires pour les questions générales
        if argumentaire_score >= sql_score or "pourquoi" in question_lower or "comment" in question_lower:
            return "argumentaire"
        else:
            return "sql"

    def _answer_argumentaire_question(self, question: str, argumentaires: Dict[str, Any]) -> str:
        """
        Répond à une question sur les argumentaires en utilisant GPT-4.

        Args:
            question: Question de l'utilisateur
            argumentaires: Dictionnaire des argumentaires chargés

        Returns:
            Réponse formatée en langage naturel
        """
        # Préparer le contexte des argumentaires
        context = json.dumps(argumentaires, indent=2, ensure_ascii=False)

        prompt = f"""Tu es un assistant CGT expert en syndicalisation et en stratégie syndicale.

Tu as accès à une base de connaissances sur les freins à la syndicalisation et les moyens de les lever.

Base de connaissances:
{context}

Question de l'utilisateur: {question}

INSTRUCTIONS:
- Réponds de manière claire, structurée et professionnelle
- Utilise les informations de la base de connaissances pour construire ta réponse
- Si la question porte sur un sujet spécifique (ex: freins, leviers, formation), cite les éléments pertinents
- Structure ta réponse avec des titres, listes et émojis appropriés pour la rendre lisible
- Sois pratique et concret : donne des exemples et des actions concrètes quand c'est pertinent
- Si la question ne peut pas être répondue avec la base de connaissances actuelle, indique-le clairement

Exemples de formatage:

Pour une question sur les freins:
"🚧 **Les principaux freins à la syndicalisation**

**Freins externes:**
- Répression patronale et peur des représailles...
- Affaiblissement des droits syndicaux...

**Freins internes:**
- Perte d'adhérents (2/3 au départ en retraite)...
- QVS négligée..."

Pour une question sur les solutions:
"💡 **Comment lever les freins à la syndicalisation**

**1. Renforcement et structuration**
- Plan de syndicalisation ciblé...
- Adapter la structuration aux réalités...

**2. Amélioration de la vie syndicale**
- Faire vivre la démocratie...
- Améliorer l'accueil..."

Maintenant, réponds à la question de l'utilisateur.
"""

        try:
            content = self._call_openai_with_fallback(
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un assistant expert CGT qui aide les militants syndicaux à comprendre les enjeux de la syndicalisation et à développer des stratégies efficaces."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.4
            )

            return content

        except Exception as e:
            logger.error(f"Erreur lors de la génération de la réponse argumentaire: {str(e)}")
            return f"❌ Erreur lors de la génération de la réponse. Détails : {str(e)}"

    def ask(self, question: str, db: Session) -> Dict[str, Any]:
        """
        Pose une question au chatbot et obtient une réponse.

        Le chatbot peut répondre à deux types de questions:
        1. Questions sur les données PAP/CSE (génère et exécute du SQL)
        2. Questions sur les argumentaires syndicaux (utilise la base de connaissances)

        Args:
            question: Question en langage naturel
            db: Session de base de données

        Returns:
            Dictionnaire contenant:
            - question: Question posée
            - answer: Réponse en langage naturel
            - sql: Requête SQL générée (si question SQL)
            - results: Résultats bruts (si question SQL)
            - metadata: Métadonnées (tokens, coût, question_type, etc.)

        Raises:
            ValueError: Si la question est vide ou la requête dangereuse
            Exception: En cas d'erreur lors du traitement
        """
        if not question or not question.strip():
            raise ValueError("La question ne peut pas être vide")

        logger.info(f"Question posée: {question}")

        try:
            # 1. Détecter le type de question
            question_type = self._detect_question_type(question)
            logger.info(f"Type de question détecté: {question_type}")

            if question_type == "argumentaire":
                # Question sur les argumentaires syndicaux
                argumentaires = self._load_argumentaires()

                if not argumentaires:
                    return {
                        "question": question,
                        "answer": "⚠️ Les argumentaires ne sont pas encore chargés dans le système. Veuillez contacter l'administrateur.",
                        "sql": None,
                        "metadata": {
                            "model": self.model,
                            "timestamp": datetime.now().isoformat(),
                            "question_type": "argumentaire",
                            "error": "argumentaires_not_loaded"
                        }
                    }

                # Répondre avec les argumentaires
                answer = self._answer_argumentaire_question(question, argumentaires)

                return {
                    "question": question,
                    "answer": answer,
                    "sql": None,
                    "results": None,
                    "metadata": {
                        "model": self.model,
                        "timestamp": datetime.now().isoformat(),
                        "question_type": "argumentaire",
                        "argumentaires_loaded": list(argumentaires.keys())
                    }
                }

            else:
                # Question sur les données PAP/CSE (SQL)
                # 1. Générer la requête SQL
                sql_info = self._generate_sql_query(question, db)

                # 2. Exécuter la requête
                results = self._execute_query(sql_info["sql"], db)

                # 3. Formater la réponse
                answer = self._format_response(question, sql_info, results)

                return {
                    "question": question,
                    "answer": answer,
                    "sql": sql_info["sql"],
                    "sql_explanation": sql_info.get("explanation"),
                    "results": results[:100],  # Limiter les résultats retournés
                    "total_results": len(results),
                    "metadata": {
                        "model": self.model,
                        "timestamp": datetime.now().isoformat(),
                        "question_type": "sql",
                        "response_type": sql_info.get("response_type")
                    }
                }

        except ValueError as e:
            # Erreur de sécurité ou validation
            logger.warning(f"Erreur de validation: {str(e)}")
            return {
                "question": question,
                "answer": f"⚠️ Erreur : {str(e)}",
                "sql": None,
                "error": str(e)
            }

        except Exception as e:
            logger.error(f"Erreur lors du traitement de la question: {str(e)}")
            return {
                "question": question,
                "answer": f"❌ Une erreur est survenue lors du traitement de votre question. Veuillez reformuler ou essayer une autre question.",
                "sql": None,
                "error": str(e)
            }


# Fonction utilitaire pour une utilisation rapide
def ask_chatbot(question: str, db: Session) -> str:
    """
    Fonction utilitaire pour poser rapidement une question au chatbot.

    Args:
        question: Question en langage naturel
        db: Session de base de données

    Returns:
        Réponse en langage naturel

    Example:
        >>> from app.db import get_session
        >>> db = next(get_session())
        >>> answer = ask_chatbot("Combien d'invitations PAP ?", db)
        >>> print(answer)
        "Il y a **320 invitations** PAP dans la base de données 📊"
    """
    chatbot = ChatbotIA()
    result = chatbot.ask(question, db)
    return result["answer"]

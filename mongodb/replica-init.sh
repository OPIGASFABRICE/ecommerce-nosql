#!/usr/bin/env bash
# ===================================================================
# Initialise le Replica Set MongoDB "rs0" (3 noeuds), puis exécute
# init.js pour créer la base et les index.
# Tourne dans un conteneur one-shot "mongo-setup" (voir docker-compose.yml).
# ===================================================================
set -e

echo ">> Attente de la disponibilité de mongo1..."
until mongosh --host mongo1 --port 27017 --quiet --eval "db.runCommand('ping').ok" > /dev/null 2>&1; do
  echo "   mongo1 pas encore prêt, on retente dans 2s..."
  sleep 2
done
echo ">> mongo1 est up."

ALREADY_INIT=$(mongosh --host mongo1 --port 27017 --quiet --eval "rs.status().ok" 2>/dev/null || echo "0")

if [ "$ALREADY_INIT" == "1" ]; then
  echo ">> Le Replica Set est déjà initialisé, rien à faire."
else
  echo ">> Initialisation du Replica Set rs0..."
  mongosh --host mongo1 --port 27017 --quiet --eval '
    rs.initiate({
      _id: "rs0",
      members: [
        { _id: 0, host: "mongo1:27017", priority: 2 },
        { _id: 1, host: "mongo2:27017", priority: 1 },
        { _id: 2, host: "mongo3:27017", priority: 1 }
      ]
    })
  '
  echo ">> Attente de l'élection du primaire..."
fi

# Attente ACTIVE d'un primaire, plutôt qu'un délai fixe (l'élection peut
# prendre de quelques secondes à ~30s selon la machine, notamment sur
# Docker Desktop / Windows).
echo ">> Vérification qu'un primaire a bien été élu (jusqu'à 90s)..."
for i in $(seq 1 45); do
  HAS_PRIMARY=$(mongosh --host mongo1 --port 27017 --quiet --eval "rs.status().members.some(m => m.stateStr === 'PRIMARY')" 2>/dev/null || echo "false")
  if [ "$HAS_PRIMARY" == "true" ]; then
    echo ">> Primaire élu après ~$((i*2))s."
    break
  fi
  echo "   pas encore de primaire, on retente dans 2s... ($i/45)"
  sleep 2
done

echo ">> Statut final du Replica Set :"
mongosh --host mongo1 --port 27017 --quiet --eval "rs.status().members.forEach(m => print(m.name + '  ->  ' + m.stateStr))"

echo ">> Exécution de init.js (création base + index)..."
mongosh "mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0" --quiet /scripts/init.js

echo ">> mongo-setup terminé avec succès."
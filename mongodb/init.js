// init.js
// Crée la base "ecommerce" et les index utiles aux agrégations de l'API.
// Exécuté une seule fois par replica-init.sh, après l'élection du RS.

db = db.getSiblingDB("ecommerce");

db.orders.createIndex({ customer_id: 1 });
db.orders.createIndex({ "items.category": 1 });
db.orders.createIndex({ date: 1 });

print("Base 'ecommerce' prête, index créés sur orders (customer_id, items.category, date).");

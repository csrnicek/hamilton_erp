# Deploy to Frappe Cloud
# Usage: /deploy
# Pushes current branch to GitHub and triggers a Frappe Cloud deploy.

cd ~/hamilton_erp && git push origin main && echo "Pushed to GitHub. Frappe Cloud will auto-deploy within 2-3 minutes. Check: https://cloud.frappe.io/dashboard/sites/hamilton-erp.v.frappe.cloud/overview"

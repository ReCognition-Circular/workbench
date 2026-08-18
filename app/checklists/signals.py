# No signals registered here.
# Cedar Track auto-fill is handled by checklists.views.fill_cedar_track()
# (called from api.views.sync_cedar), replacing the old post_save hook
# that read DataWipeRecord.json_data["audit"].

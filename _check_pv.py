import poster_vinted
funcs = ['get_live_events','get_posting_status','poster_avec_retry','analyse_probleme_posting','apply_fix','generer_username_naturel','generer_bio_naturelle','session_posting']
for f in funcs:
    has = hasattr(poster_vinted, f)
    tag = "[OK]" if has else "[KO]"
    print(tag + " " + f)

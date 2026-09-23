DEFAULT_MODS = {
    "spawn_min_sec": 120,
    "spawn_max_sec": 240,
    "trade_timeout_sec": 60,
    "fight_ignore_sec": 60,
    "gambling": True,
    "trading": True,
    "powerups": True,
    "shop_price_mult": 1.0,
    "cage_income_divisor": 50.0,
    "cage_interval_sec": 60,
    "luck_global": 1.0,
    "luck_spawn": 1.0,
    "luck_gamble": 1.0,
    "luck_double": 1.0,
    "gamble_cd_sec": 300,
    "birdpass_xp_mult": 1.0,
    "birdpass_reward_mult": 1.0,
}

REQUIRED = {
    "spawn_min_sec": (int, 1, 86400),
    "spawn_max_sec": (int, 1, 86400),
    "trade_timeout_sec": (int, 5, 3600),
    "fight_ignore_sec": (int, 5, 3600),
    "gambling": (bool,),
    "trading": (bool,),
    "powerups": (bool,),
    "shop_price_mult": (float, 0.05, 100.0),
    "cage_income_divisor": (float, 1.0, 1.0e9),
    "cage_interval_sec": (int, 10, 86400),
    "luck_global": (float, 0.1, 10.0),
    "luck_spawn": (float, 0.1, 10.0),
    "luck_gamble": (float, 0.1, 10.0),
    "luck_double": (float, 0.1, 10.0),
    "gamble_cd_sec": (int, 0, 86400),
    "birdpass_xp_mult": (float, 0.1, 100.0),
    "birdpass_reward_mult": (float, 0.1, 100.0),
}


def overrides_for(values):
    out = {}
    for key, default in DEFAULT_MODS.items():
        if key not in values:
            continue
        v = values[key]
        if isinstance(default, bool) and isinstance(v, bool) and v != default:
            out[key] = v
        elif isinstance(default, bool):
            out[key] = bool(v)
        elif isinstance(default, int) and isinstance(v, int) and v != default:
            out[key] = v
        elif isinstance(default, int) and isinstance(v, (int, float)) and v != default:
            out[key] = int(v)
        elif isinstance(default, float) and isinstance(v, (int, float)) and float(v) != default:
            out[key] = float(v)
    return out


def _typed_value(key, value):
    spec = REQUIRED.get(key)
    if spec is None:
        return None
    kind = spec[0]
    if kind is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if kind is int:
        try:
            v = int(value)
        except (TypeError, ValueError):
            return None
        lo, hi = spec[1], spec[2]
        return min(max(v, lo), hi)
    if kind is float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        lo, hi = spec[1], spec[2]
        return min(max(v, lo), hi)
    return None


def validate_and_clean(values):
    cleaned = {}
    for key in DEFAULT_MODS:
        if key not in values:
            continue
        v = _typed_value(key, values[key])
        if v is not None:
            cleaned[key] = v
    return cleaned


def get_mods(bot, guild_id):
    over = {}
    cache = getattr(bot, "mods_cache", None)
    if cache:
        over = cache.get(int(guild_id), {}) or {}
    merged = dict(DEFAULT_MODS)
    merged.update(over)
    return merged


def is_modified(bot, guild_id):
    cache = getattr(bot, "mods_cache", None)
    if not cache:
        return False
    return bool(cache.get(int(guild_id)))


def modified_guild_ids(bot):
    cache = getattr(bot, "mods_cache", None)
    if not cache:
        return set()
    return {int(g) for g, over in cache.items() if over}


def save(bot, guild_id, values):
    cleaned = validate_and_clean(values)
    over = overrides_for(cleaned)
    bot.db.set_server_mods(int(guild_id), over)
    cache = getattr(bot, "mods_cache", None)
    if cache is None:
        cache = {}
        bot.mods_cache = cache
    if over:
        cache[int(guild_id)] = over
    else:
        cache.pop(int(guild_id), None)
    return get_mods(bot, guild_id)
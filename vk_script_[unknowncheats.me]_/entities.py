#built-in
from collections import namedtuple
from math import hypot

#ext
from pyMeow import r_string, r_float, r_bool, r_int, r_ints64

#own
from data import Offsets


class AttributesReader(Offsets):
    def __init__(self, process, base_address):
        self.process = process
        self.base_address = base_address
        self.spell_keys = ['Q', 'W', 'E', 'R', 'D', 'F']
        self.PlayerNamedtuple = namedtuple('Player', 'name basic_attack bonus_attack x y z attack_range')
        self.EnemyNamedtuple = namedtuple('Enemy', 'name health max_health gold armor basic_attack bonus_attack magic_damage x y z alive targetable visible attack_range pointer')
        self.MinionNamedtuple = namedtuple('Minion', 'health armor x y z alive targetable visible')
        self.TurretNamedTuple = namedtuple('Turret', 'attack_range x y z alive targetable visible')

    def read_player(self, local_player):
        process = self.process
        attributes = self.PlayerNamedtuple(
            name =         r_string(process, local_player + self.obj_name),
            basic_attack = r_float(process, local_player + self.obj_base_attack),
            bonus_attack = r_float(process, local_player + self.obj_bonus_attack),
            x =            r_float(process, local_player + self.obj_x),
            y =            r_float(process, local_player + self.obj_y),
            z =            r_float(process, local_player + self.obj_z),
            attack_range = r_float(process, local_player + self.obj_attack_range)
        )

        return attributes
    
    def read_enemy(self, pointer):
        process = self.process
        attributes = self.EnemyNamedtuple(
            name =         r_string(process, pointer + self.obj_name),
            health =       r_float(process, pointer + self.obj_health),
            max_health =   r_float(process, pointer + self.obj_max_health),
            gold =         r_int(process, pointer + self.obj_gold),
            armor =        r_float(process, pointer + self.obj_armor),
            basic_attack = r_float(process, pointer + self.obj_base_attack),
            bonus_attack = r_float(process, pointer + self.obj_bonus_attack),
            magic_damage = r_float(process, pointer + self.obj_magic_damage),
            x =            r_float(process, pointer + self.obj_x),
            y =            r_float(process, pointer + self.obj_y),
            z =            r_float(process, pointer + self.obj_z),
            alive =        r_int(process, pointer + self.obj_spawn_count) % 2 == 0,
            targetable =   r_bool(process, pointer + self.obj_targetable),
            visible =      r_bool(process, pointer + self.obj_visible),
            attack_range = r_float(process, pointer + self.obj_attack_range),
            pointer =      pointer

        )
    
        return attributes
    
    def read_minion(self, pointer):
        process = self.process
        attributes = self.MinionNamedtuple(
            health =       r_float(process, pointer + self.obj_health),
            armor =        r_float(process, pointer + self.obj_armor),
            x =            r_float(process, pointer + self.obj_x),
            y =            r_float(process, pointer + self.obj_y),
            z =            r_float(process, pointer + self.obj_z),
            alive =        r_int(process, pointer + self.obj_spawn_count) % 2 == 0,
            targetable =   r_bool(process, pointer + self.obj_targetable),
            visible =      r_bool(process, pointer + self.obj_visible),
        )

        return attributes
    
    def read_turret(self, pointer):
        process = self.process
        attributes = self.TurretNamedTuple(
            attack_range = r_float(process, pointer + self.obj_attack_range),
            x =            r_float(process, pointer + self.obj_x),
            y =            r_float(process, pointer + self.obj_y),
            z =            r_float(process, pointer + self.obj_z),
            alive =        r_int(process, pointer + self.obj_spawn_count) % 2 == 0,
            targetable =   r_bool(process, pointer + self.obj_targetable),
            visible =      r_bool(process, pointer + self.obj_visible),
        )

        return attributes

    def read_spells(self, pointer):
        # Currently this only works for spells level.
        # [v13.21] - removed.
        spells, process = [], self.process
        spell_book = r_ints64(process, pointer + self.obj_spell_book, 0x4)
        for spell_slot in spell_book:
            level = r_int(process, spell_slot + self.spell_level)
            spells.append(level)
        return spells
    

    
class EntityConditions:
    def __init__(self, world=None, stats=None):
        if stats is not None:
            self.radius = stats.get_targets_radius()

        if world is not None:
            self.world_to_screen_limited = world.world_to_screen_limited
            self.get_view_proj_matrix = world.get_view_proj_matrix

        self.drawings_mode = False
        self.player = None

    @staticmethod
    def hurtable(entity) -> bool:
        return entity.alive and entity.visible and entity.targetable

    @staticmethod
    def effective_damage(damage, armor) -> float:
        if armor >= 0:
            return damage * 100. / (100. + armor)
        return damage * (2. - (100. / (100. - armor)))

    @staticmethod
    def max_damage(entity) -> float:
        return max(entity.basic_attack + entity.bonus_attack, entity.magic_damage)

    def distance(self, entity) -> float:
        return hypot(self.player.x - entity.x, self.player.y - entity.y)
    
    def entity_in_range(self, entity) -> bool:
        # if greater precision is required: (only for champions)
        # return self.distance(self.player, entity) - self.radius.get(entity.name, 65.0) <= self.player.attack_range + self.radius.get(self.player.name, 65.0)
        return self.distance(entity) - 65.0 <= self.player.attack_range + 65.0

    def min_attacks(self, entity) -> float:
        return entity.health / self.effective_damage(self.player.basic_attack + self.player.bonus_attack, entity.armor)

    def ready_to_attack(self, entity) -> bool:
        if self.drawings_mode:
            # Know if enemy champions are hurtable and if are in the screen.
            return self.hurtable(entity) and self.world_to_screen_limited(self.get_view_proj_matrix(), entity.x, entity.z, entity.y)
        return self.hurtable(entity) and self.entity_in_range(entity)

class TargetSelector(EntityConditions):
    def __init__(self, world=None, stats=None):
        super().__init__(world, stats)

    def select_by_health(self, player, entities):
        # Less health / armor entity will be focused. (less hits to kill)
        self.player = player
        return min(filter(self.ready_to_attack, entities), key=self.min_attacks, default=None)
    
    def select_by_damage(self, player, entities):
        # Enemy with most damage will be focused.
        self.player = player
        return max(filter(self.ready_to_attack, entities), key=self.max_damage, default=None)
    
    def select_by_distance(self, player, entities):
        # Nearest enemy will be focused.
        self.player = player
        return min(filter(self.ready_to_attack, entities), key=self.distance, default=None)

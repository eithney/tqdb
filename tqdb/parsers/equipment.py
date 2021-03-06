"""
All wearable/usable equipment parsers.

"""
import logging
import math
import os

import numexpr

from tqdb import dbr as DBRParser
from tqdb.constants.resources import DB
from tqdb.parsers.main import TQDBParser
from tqdb.utils.text import texts

# Shared constant to determine what difficulty an item drops in:
DIFFICULTIES = {
    # Normal Difficulty
    'n': 'tagRDifficultyTitle01',
    # Epic Difficulty
    'e': 'tagRDifficultyTitle02',
    # Legendary Difficulty
    'l': 'tagRDifficultyTitle03',
}

ARTIFACT_CLASSIFICATIONS = {
    'Lesser': 'xtagArtifactClass01',
    'Greater': 'xtagArtifactClass02',
    'Divine': 'xtagArtifactClass03',
}


class ItemArtifactParser(TQDBParser):
    """
    Parser for `itemartifact.tpl`.

    """
    def __init__(self):
        super().__init__()

    @staticmethod
    def get_template_path():
        return f'{TQDBParser.base}\\itemartifact.tpl'

    def parse(self, dbr, dbr_file, result):
        file_name = os.path.basename(dbr_file).split('_')

        # Skip artifacts with unknown difficulties in which they drop:
        if file_name[0] not in DIFFICULTIES:
            raise StopIteration

        # Artifact classification value (always Lesser, Greater or Divine)
        ac_value = dbr.get('artifactClassification', None)
        # Translation tag for this classification
        ac_tag = ARTIFACT_CLASSIFICATIONS[ac_value]

        result.update({
            # Bitmap has a different key name than items here.
            'bitmap': dbr.get('artifactBitmap', None),
            # Classification is either Lesser, Greater or Divine (translated)
            'classification': texts.get(ac_tag),
            # Difficulty it starts dropping is based on the file name
            'dropsIn': texts.get(DIFFICULTIES[file_name[0]]).strip(),
            # For artifacts the tag is in the Actor.tpl variable 'description'
            'name': texts.get(dbr['description']),
            'tag': dbr['description'],
        })


class ItemArtifactFormulaParser(TQDBParser):
    """
    Parser for `itemartifactformula.tpl`.

    """
    ARTIFACT = 'artifactName'
    BITMAP = 'artifactFormulaBitmapName'

    def __init__(self):
        super().__init__()

    @staticmethod
    def get_template_path():
        return f'{TQDBParser.base}\\itemartifactformula.tpl'

    def parse(self, dbr, dbr_file, result):
        # Skip formula without artifacts
        if self.ARTIFACT not in dbr:
            raise StopIteration

        artifact = DBRParser.parse(dbr[self.ARTIFACT])

        # Update the result with the artifact:
        result['tag'] = artifact['tag']
        result['name'] = artifact['name']
        result['classification'] = artifact['classification']

        if self.BITMAP in dbr:
            result['bitmap'] = dbr[self.BITMAP]

        # Grab the reagents (ingredients):
        for reagent_key in ['reagent1', 'reagent2', 'reagent3']:
            # For some reason reagent DBRs are of type array, so grab [0]:
            reagent = DBRParser.parse(dbr[reagent_key + 'BaseName'][0])

            # Add the reagent (relic, scroll or artifact)
            result[reagent_key] = reagent['tag']

        # Add the potential completion bonuses
        bonuses = DBRParser.parse(dbr['artifactBonusTableName'])
        result['bonus'] = bonuses.get('table', [])

        # Last but not least, pop the 'properties' from this result, since
        # formula don't have the properties themselves, but their respective
        # artifacts do.
        result.pop('properties')


class ItemBaseParser(TQDBParser):
    """
    Parser for `templatebase/itembase.tpl`.

    """
    CLASSIFICATIONS = {
        'Magical': 'tagTutorialTip05TextE',
        'Rare': 'tagTutorialTip05TextF',
        'Epic': 'tagRDifficultyTitle02',
        'Legendary': 'tagRDifficultyTitle03',
    }

    # Classification checks don't count for these classes:
    ALLOWED = [
        'ItemArtifact',
        'ItemArtifactFormula',
        'ItemRelic',
        'ItemCharm',
        'OneShot_Scroll',
    ]

    REQUIREMENTS = [
        'dexterityRequirement',
        'intelligenceRequirement',
        'levelRequirement',
        'strengthRequirement',
    ]

    def __init__(self):
        super().__init__()

    @staticmethod
    def get_template_path():
        return f'{TQDBParser.base}\\templatebase\\itembase.tpl'

    def parse(self, dbr, dbr_file, result):
        self.is_valid_classification(dbr, dbr_file, result)

        # Always set the category:
        result['category'] = dbr.get('Class', None)

        # Flat requirements are a part of ItemBase, variable ones aren't:
        for requirement in self.REQUIREMENTS:
            if requirement in dbr:
                result[requirement] = dbr[requirement]

    def is_valid_classification(self, dbr, dbr_file, result):
        """
        Check if this item is of a valid classification for TQDB.

        """
        itemClass = dbr.get('Class')
        classification = dbr.get('itemClassification', None)

        if (itemClass not in self.ALLOWED and
                classification not in self.CLASSIFICATIONS.keys()):
            raise StopIteration
        elif (classification in self.CLASSIFICATIONS.keys() and
                'classification' not in result):
            # Only add the classification if it doesn't exist yet:
            result['classification'] = texts.get(
                self.CLASSIFICATIONS[classification]).strip()

            # For Monster Infrequents, make sure a drop difficulty exists:
            if classification == 'Rare':
                file_name = os.path.basename(dbr_file).split('_')
                if len(file_name) < 2 or file_name[1] not in DIFFICULTIES:
                    raise StopIteration

                # Set the difficulty for which this MI drops:
                result['dropsIn'] = texts.get(
                    DIFFICULTIES[file_name[1]]).strip()


class ItemEquipmentParser(TQDBParser):
    """
    Parser for `templatebase/itemequipment.tpl`.

    """
    # The prefixes for the types of requirements for items:
    REQUIREMENTS = [
        'Dexterity',
        'Intelligence',
        'Level',
        'Strength',
    ]

    # The base requirements cost file, as a fallback:
    REQUIREMENT_FALLBACK = DB / 'records/game/itemcost.dbr'

    def __init__(self):
        super().__init__()

    def get_priority(self):
        """
        Override this parsers priority to set as lowest.

        """
        return TQDBParser.LOWEST_PRIORITY

    @staticmethod
    def get_template_path():
        return f'{TQDBParser.base}\\templatebase\\itemequipment.tpl'

    def parse(self, dbr, dbr_file, result):
        # If no tag exists, skip parsing:
        tag = dbr.get('itemNameTag', None)
        if not tag:
            raise StopIteration

        # Set the known item properties:
        result.update({
            'bitmap': dbr.get('bitmap', None),
            'itemLevel': dbr.get('itemLevel', None),
            'name': texts.get(tag),
            'tag': tag,
        })

        # Check if this item is part of a set:
        item_set_path = dbr.get('itemSetName', None)
        if item_set_path:
            # Read (don't parse to avoid recursion) the set to get the tag:
            item_set = DBRParser.read(item_set_path)

            # Only add the set if it has a tag:
            result['set'] = item_set.get(ItemSetParser.NAME, None)

        # Stop parsing here if requirement parsing isn't necessary
        if not self.should_parse_requirements(dbr, result):
            return

        # Cost prefix of this props is determined by its class
        cost_prefix = dbr['Class'].split('_')[1]
        cost_prefix = cost_prefix[:1].lower() + cost_prefix[1:]

        # Read cost file
        cost_properties = DBRParser.read(dbr.get(
            'itemCostName', self.REQUIREMENT_FALLBACK))

        # Grab the props level (it's a variable in the equations)
        for requirement in self.REQUIREMENTS:
            # Create the equation key
            equation_key = cost_prefix + requirement + 'Equation'
            req = requirement.lower() + 'Requirement'

            # Existing requirements shouldn't be overriden:
            if equation_key in cost_properties and req not in result:
                equation = cost_properties[equation_key]

                # camelCased variables are required for the equations:
                itemLevel = dbr['itemLevel']  # noqa
                totalAttCount = len(result['properties'])  # noqa

                # Eval the equation:
                result[req] = math.ceil(numexpr.evaluate(equation).item())

    def should_parse_requirements(self, dbr, result):
        """
        Check if this parser should parse requirements further.

        If either an requirement equation file is present, or no requirements
        have been defined statically in the DBR, requirements should be parsed.

        The latter scenario falls back to the generic `itemcost.dbr` file in
        the game folder.

        """
        return 'itemCostName' in dbr or not any(
            f'{requirement.lower}Requirement' in dbr
            for requirement in self.REQUIREMENTS)


class ItemRelicParser(TQDBParser):
    """
    Parser for `itemrelic.tpl`.

    """
    DIFFICULTIES_LIST = list(DIFFICULTIES.values())

    def __init__(self):
        super().__init__()

    @staticmethod
    def get_template_path():
        return f'{TQDBParser.base}\\itemrelic.tpl'

    def get_priority(self):
        """
        Override this parsers priority to set as lowest.

        """
        return TQDBParser.LOWEST_PRIORITY

    def parse(self, dbr, dbr_file, result):
        file_name = os.path.basename(dbr_file).split('_')
        difficulty = self.DIFFICULTIES_LIST[int(file_name[0][1:]) - 1]

        result.update({
            # The act it starts dropping in is also listed in the file name
            'act': file_name[1],
            # Bitmap has a different key name than items here.
            'bitmap': dbr.get('relicBitmap', None),
            # Difficulty classification is based on the file name
            'classification': texts.get(difficulty).strip(),
            # Ironically the itemText holds the actual description tag
            'description': texts.get(dbr['itemText']),
            # For relics the tag is in the Actor.tpl variable 'description'
            'name': texts.get(dbr['description']),
            'tag': dbr['description'],
        })

        # The possible completion bonuses are in bonusTableName:
        bonuses = DBRParser.parse(dbr['bonusTableName'])
        result['bonus'] = bonuses.get('table', [])

        # Find how many pieces this relic has
        max_pieces = TQDBParser.highest_tier(
            result['properties'], result['properties'].keys())

        # Initialize a list of tiers
        properties = [{} for i in range(max_pieces)]

        # Setup properties as list to correspond to adding pieces of a relic:
        for key, values in result['properties'].items():
            if not isinstance(values, list):
                # This property is just repeated for all tiers:
                for i in range(max_pieces):
                    properties[i][key] = values
                continue

            for index, value in enumerate(values):
                properties[index][key] = value

        result['properties'] = properties


class ItemSetParser(TQDBParser):
    """
    Parser for `itemset.tpl`

    """
    NAME = 'setName'

    def __init__(self):
        super().__init__()

    def get_priority(self):
        """
        Override this parsers priority to set as lowest.

        """
        return TQDBParser.LOWEST_PRIORITY

    @staticmethod
    def get_template_path():
        return f'{TQDBParser.base}\\itemset.tpl'

    def parse(self, dbr, dbr_file, result):
        tag = dbr.get(self.NAME, None)

        if not tag or texts.get(tag) == tag:
            logging.warning(f'No tag or name for set found in {dbr_file}.')
            raise StopIteration

        result.update({
            # Prepare the list of set items
            'items': [],
            'name': texts.get(tag),
            'tag': tag,
        })

        # Add the set members:
        for set_member_path in dbr['setMembers']:
            # Parse the set member:
            set_member = DBRParser.parse(set_member_path)

            # Add the tag to the items list:
            result['items'].append(set_member['tag'])

        # The number of set bonuses is equal to the number of set items minus 1
        bonus_number = len(result['items']) - 1

        # Because this parser has the lowest priority, all properties will
        # already have been parsed, so they can now be reconstructed to match
        # the set bonuses. Begin by initializing the properties for each set
        # bonus tier to an empty dict:
        properties = [{} for i in range(bonus_number)]

        # Insert the existing properties by adding them to the correct tier:
        for field, values in result['properties'].items():
            if not isinstance(values, list):
                properties[bonus_number - 1][field] = values

                # Don't parse any further
                continue

            # The starting tier is determined by the highest tier
            starting_index = bonus_number - len(values)

            # Now just iterate and add the properties to each tier:
            for index, value in enumerate(values):
                properties[starting_index + index][field] = value

        # Now set the tiered set bonuses:
        result['properties'] = properties

        # Pop off the first element of the properties, if it's empty:
        if len(result['properties']) > 1:
            if not result['properties'][0]:
                result['properties'].pop(0)


class OneShotScrollParser(TQDBParser):
    """
    Parser for `oneshot_scroll.tpl`.

    """
    DIFFICULTIES_LIST = list(DIFFICULTIES.values())

    def __init__(self):
        super().__init__()

    @staticmethod
    def get_template_path():
        # Note: this technically handles parameters from oneshot.tpl too.
        return f'{TQDBParser.base}\\oneshot_scroll.tpl'

    def parse(self, dbr, dbr_file, result):
        """
        Parse the scroll.

        """
        # Use the file name to determine the difficulty:
        file_name = os.path.basename(dbr_file).split('_')[0][1:]
        # Strip all but digits from the string, then cast to int:
        difficulty = self.DIFFICULTIES_LIST[int(
            ''.join(filter(lambda x: x.isdigit(), file_name))) - 1]

        result.update({
            'tag': dbr['description'],
            'name': texts.get(dbr['description']),
            'classification': texts.get(difficulty).strip(),
            'description': texts.get(dbr['itemText']),
        })

        # Greater scroll of svefnthorn is incorrectly referenced as its Divine
        # variant. Manual fix required for now:
        if '02_svefnthorn.dbr' in str(dbr_file):
            result['tag'] = 'x2tagScrollName06'
            result['name'] = texts.get('x2tagScrollName06')

        # Set the bitmap if it exists
        if 'bitmap' in dbr:
            result['bitmap'] = dbr['bitmap']

        # Grab the skill file:
        skill = DBRParser.parse(dbr['skillName'])

        # Add the first tier of properties if there are any:
        if 'properties' in skill and skill['properties']:
            result['properties'] = skill['properties'][0]

        # Add any summon (just the first one)
        if 'summons' in skill:
            result['summons'] = skill['summons'][0]


class ShieldParser(TQDBParser):
    """
    Parser for `weaponarmor_shield.tpl`.

    """
    # The tag of the resource text that will show block chance & values:
    TEXT = 'tagShieldBlockInfo'
    BLOCK = 'defensiveBlock'

    def __init__(self):
        super().__init__()

    @staticmethod
    def get_template_path():
        return f'{TQDBParser.base}\\weaponarmor_shield.tpl'

    def parse(self, dbr, dbr_file, result):
        # Set the block chance and value:
        result['properties'][self.BLOCK] = texts.get(self.TEXT).format(
            # Block chance
            dbr.get(f'{self.BLOCK}Chance', 0),
            # Blocked damage
            dbr.get(self.BLOCK, 0))


class WeaponParser(TQDBParser):
    """
    Parser for `templatebase/weapon.tpl`.

    """
    def __init__(self):
        super().__init__()

    @staticmethod
    def get_template_path():
        return f'{TQDBParser.base}\\templatebase\\weapon.tpl'

    def parse(self, dbr, dbr_file, result):
        dbr_class = dbr['Class']

        # Skip shields:
        if (dbr_class.startswith('Weapon') and 'Shield' in dbr_class):
            return

        # Set the attack speed
        result['properties']['characterAttackSpeed'] = texts.get(
            dbr['characterBaseAttackSpeedTag'])

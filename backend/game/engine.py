class GameState:
    """État d'une partie : configuration, progression des scènes, historique des messages.

    Aucun appel réseau ici : l'automate est testable à sec.
    Phases : intro (index 0) -> scene (1..total-1) -> climax (total) -> epilogue (total+1).
    """

    def __init__(self, players: int, names: list, genre: str, duration: int):
        self.players = players
        self.names = names
        self.genre = genre
        self.duration = duration
        self.total_scenes = max(2, duration // 5)
        self.scene_index = 0
        self.messages: list = []

    def phase(self) -> str:
        if self.scene_index == 0:
            return "intro"
        if self.scene_index < self.total_scenes:
            return "scene"
        if self.scene_index == self.total_scenes:
            return "climax"
        return "epilogue"

    def advance(self) -> None:
        self.scene_index += 1

    @property
    def finished(self) -> bool:
        return self.scene_index > self.total_scenes + 1

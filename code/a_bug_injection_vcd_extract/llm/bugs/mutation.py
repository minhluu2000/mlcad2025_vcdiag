import yaml
import os.path

class Mutation:
    def __init__(self, name: str, description: str, mutation_dir: str, isolated: bool=True):
        self.name = name
        self.description = description
        self.instruction_file = os.path.join(mutation_dir, f'{name}.txt')
        self.isolated = isolated
    
    def get_instructions(self) -> str:
        with open(self.instruction_file, 'r') as f:
            return f.read()

class MutationList:
    mutations: list[Mutation]

    def __init__(self, mutations: list[Mutation]=None):
        self.mutations = mutations or []
    
    def add(self, mutation: Mutation):
        self.mutations.append(mutation)
    
    def __getitem__(self, index : int) -> Mutation:
        return self.mutations[index]
    
    def find_by_name(self, mutation_name: str) -> Mutation:
        for mutation in self.mutations:
            if mutation.name == mutation_name:
                return mutation
        return None

    def stringify(self) -> str:
        muts_str = ''
        for i, mutation in enumerate(self.mutations):
            muts_str += f'{i+1}. {mutation.name}: {mutation.description}\n'
        return muts_str

def load_mutations(mutation_dir: str) -> MutationList:
    with open(os.path.join(mutation_dir, 'index.yaml'), 'r') as f:
        data = yaml.safe_load(f)
    
    mutations = MutationList([Mutation(item['name'], item['description'], mutation_dir, item['isolated']) for item in data])
    return mutations
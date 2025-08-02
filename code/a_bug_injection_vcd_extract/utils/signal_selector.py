import os
import anytree
from vcd_extract.utils import verible_verilog_syntax

class SignalSelector:
    def __init__(self, verible_verilog_syntax_path: str,
                 design_path: str,
                 input_signals_list_path: str,
                 output_signals_list_path: str,
                 debug=False):

        self.parser = verible_verilog_syntax.VeribleVerilogSyntax(
            executable=verible_verilog_syntax_path
        )

        self.design_path = design_path
        self.input_signals_list_path = input_signals_list_path
        self.output_signals_list_path = output_signals_list_path

        self.debug = debug

    def _get_design_files(self):
        self.design_files = []
        for root, _, files in os.walk(self.design_path):
            for file in files:
                if file.endswith('.v') or file.endswith('.sv'):
                    self.design_files.append(os.path.join(root, file))

    def construct_module_db(self):
        self._get_design_files()
        design_files_data = self.parser.parse_files(self.design_files,
                                                    options={
                                                        "gen_tree": True,
                                                        "skip_null": True,
                                                        "gen_tokens": True
                                                    }
                                                    )

        self.module_db = {}
        for file_path, file_data in design_files_data.items():
            try:
                # for each source file, extract data from each declared module
                for prefix, _, node in anytree.RenderTree(file_data.tree):
                    if "kModuleDeclaration" in str(node):
                        current_module = node
                        if "kModuleHeader" in str(node.children[0]):
                            if "SymbolIdentifier" in str(node.children[0].children[1]):
                                module_name = str(node.children[0].children[1]).split(
                                    " ")[-1].strip("\'")
                                # print("Module name: ", module_name)
                                self.module_db[module_name] = None

                        data_dec_sub_trees = []

                        # Look for all data declaration subtress
                        for current_module_prefix, _, current_module_node in anytree.RenderTree(current_module):
                            if "kDataDeclaration" in str(current_module_node):
                                data_dec_sub_trees.append(current_module_node)

                        # A dict to store the variable name and its type
                        type_var_db = {}

                        for data_dec_sub_tree in data_dec_sub_trees:
                            # kInstantiationType
                            type_tree = data_dec_sub_tree.children[0].children[0]
                            # kGateInstanceRegisterVariableList
                            varible_list_tree = data_dec_sub_tree.children[0].children[1]

                            # iterate through type tree to find the variable type
                            for _, _, type_tree_node in anytree.RenderTree(type_tree):
                                if "kDataType" in str(type_tree_node):
                                    if "kDataTypePrimitive" in str(type_tree_node.children[0]):
                                        found_type = str(type_tree_node.children[0].children[0]).split(" ")[
                                            0].strip("[]")
                                        if found_type not in type_var_db:
                                            type_var_db[found_type] = []
                                            # print("Primitive type: ", found_type)
                                    else:
                                        for _, _, type_tree_node_children in anytree.RenderTree(type_tree_node):
                                            if "kQualifiedId" in str(type_tree_node_children):
                                                found_type = ""
                                                for child_node in type_tree_node_children.children:
                                                    if "kUnqualifiedId" in str(child_node):
                                                        found_type += str(child_node.children[0]).split(
                                                            " ")[-1].strip("\'")
                                                    else:
                                                        found_type += str(child_node).split(" ")[
                                                            0].strip("[]")
                                                if found_type not in type_var_db:
                                                    type_var_db[found_type] = [
                                                    ]
                                                break
                                            elif "kUnqualifiedId" in str(type_tree_node_children):
                                                if "SymbolIdentifier" in str(type_tree_node_children.children[0]):
                                                    found_type = str(type_tree_node_children.children[0]).split(
                                                        " ")[-1].strip("\'")
                                                    if found_type not in type_var_db:
                                                        type_var_db[found_type] = [
                                                        ]
                                                    break

                            # iterate through variable list tree to find the variable name
                            for varible_list_tree_prefix, _, varible_list_tree_node in anytree.RenderTree(varible_list_tree):
                                if "kRegisterVariable" in str(varible_list_tree_node):
                                    if "SymbolIdentifier" in str(varible_list_tree_node.children[0]):
                                        found_var = str(varible_list_tree_node.children[0]).split(
                                            " ")[-1].strip("\'")
                                        type_var_db[found_type].append(
                                            found_var)
                                if "kGateInstance" in str(varible_list_tree_node):
                                    if "SymbolIdentifier" in str(varible_list_tree_node.children[0]):
                                        found_var = str(varible_list_tree_node.children[0]).split(
                                            " ")[-1].strip("\'")
                                        type_var_db[found_type].append(
                                            found_var)

                        # Add to self.module_db
                        self.module_db[module_name] = type_var_db
            except Exception as e:
                print(f"Error: {file_path} with error: {e}")
                continue

    def print_module_db(self):
        for module_name, module_data in self.module_db.items():
            print(f"Module: {module_name}")
            for type_name, var_list in module_data.items():
                print(f"  {type_name}: {var_list}")

    def signal_selector(self, target_modules: list, exclude_keywords: list, include_keywords: list):
        self.construct_module_db()
        self.print_module_db()

        declared_vars = []
        for target_module in target_modules:
            for module_name, module_data in self.module_db.items():
                try:
                    for type_name, var_list in module_data.items():
                        if target_module == type_name:
                            declared_vars += var_list
                            break
                except Exception as e:
                    print(f"Error: {module_name} with error: {e}")
                    continue

        self.pruned_signal_list = []
        with open(self.input_signals_list_path, 'r') as f:
            lines = f.readlines()
            self.pruned_signal_list = [line for line in lines if any(
                var in line for var in declared_vars)]
            
            self.pruned_signal_list = [line for line in self.pruned_signal_list if not any(
                keyword in line for keyword in exclude_keywords)]
            
            self.pruned_signal_list = self.pruned_signal_list + [line for line in lines if any(
                keyword in line for keyword in include_keywords)]
            
        # Make a set to remove duplicates
        self.pruned_signal_list = list(set(self.pruned_signal_list))

        # Export the signal_list and pruned_signals to two separate files
        with open(self.output_signals_list_path, 'w') as f:
            for signal in self.pruned_signal_list:
                f.write(signal)
                
        # Check if the pruned signals file was generated
        if not os.path.exists(self.output_signals_list_path):
            raise FileNotFoundError(
                f"Pruned signals failed to generate at {self.output_signals_list_path}")
        print(f"Pruned signals generated at {self.output_signals_list_path}")

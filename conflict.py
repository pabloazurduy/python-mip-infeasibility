import logging
import sys
from copy import copy, deepcopy
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import random

import mip
import numpy as np

# logger = logging.getLogger(__name__)
logger = logging.getLogger('conflict')

class ConflictFinder:

    def __init__(self):
        pass

    def find_iis(self,
                 model: "mip.Model", 
                 method: str = "deletion-filter",) -> mip.ConstrList:
                
        # check if infeasible 
        assert model.status == mip.OptimizationStatus.INFEASIBLE, 'model is not infeasible'
        # assert ,is not because time limit 
        if method == "deletion-filter":
            return self.deletion_filter(model)
        if method == "additive-algorithm":
            return self.additive_algorithm(model)        
            
    def deletion_filter(self, 
                        model:"mip.Model")-> mip.ConstrList:
        
        # 1. create a model with all constraints but one 
        aux_model = model.copy()
        aux_model.objective = 1
        aux_model.emphasis = 1 # feasibility
        aux_model.preprocess = 1 # -1  automatic, 0  off, 1  on.

        logger.debug('starting deletion_filter algorithm')
        
        for inc_crt in model.constrs:
            aux_model_inc_crt = aux_model.constr_by_name(inc_crt.name) # find constraint by name 
            aux_model.remove(aux_model_inc_crt) # temporally remove inc_crt  
            
            aux_model.optimize() 
            status = aux_model.status
            # 2. test feasibility, if feasible, return dropped constraint to the set 
            # 2.1 else removed it permanently 
            # logger.debug('status {}'.format(status))
            if status == mip.OptimizationStatus.INFEASIBLE:
                logger.debug('removing permanently {}'.format(inc_crt.name))
                continue
            elif status in [mip.OptimizationStatus.FEASIBLE, mip.OptimizationStatus.OPTIMAL] :
                aux_model.add_constr(inc_crt.expr, name= inc_crt.name)

        iis = aux_model.constrs

        return iis 


    def additive_algorithm(self,
                           model:"mip.Model")-> mip.ConstrList:
        
        # Create some aux models to test feasibility of the set of constraints  
        aux_model_testing =  mip.Model()
        for var in model.vars:
            aux_model_testing.add_var(name=var.name, 
                                      lb = var.lb,
                                      ub = var.ub, 
                                      var_type=var.var_type,
                                      # obj= var.obj, 
                                      # column=var.column   #!! libc++abi.dylib: terminating with uncaught exception of type CoinError
                                      )
        aux_model_testing.objective = 1
        aux_model_testing.emphasis = 1 # feasibility
        aux_model_testing.preprocess = 1 # -1  automatic, 0  off, 1  on.
        aux_model_iis = aux_model_testing.copy() # a second aux model to test feasibility of the incumbent iis
        
        # algorithm start 
        all_constraints = model.constrs
        testing_crt_set = mip.ConstrList(model=aux_model_testing) #T
        iis = mip.ConstrList(model=aux_model_iis) #I
        
        while True:
            for crt in all_constraints:
                testing_crt_set.add(crt.expr, name=crt.name)
                aux_model_testing.constrs = testing_crt_set
                aux_model_testing.optimize()

                if aux_model_testing.status ==  mip.OptimizationStatus.INFEASIBLE:
                    iis.add(crt.expr, name=crt.name)
                    aux_model_iis.constrs = iis
                    aux_model_iis.optimize()

                    if aux_model_iis.status == mip.OptimizationStatus.INFEASIBLE:
                        return iis  
                    elif aux_model_iis.status in [mip.OptimizationStatus.FEASIBLE,mip.OptimizationStatus.OPTIMAL] :
                        testing_crt_set = mip.ConstrList(model=aux_model_testing)
                        for crt in iis: # basically this loop is for set T=I // aux_model_iis =  iis.copy() 
                            testing_crt_set.add(crt.expr, name=crt.name)
                        break     
            
    def deletion_filter_milp_ir_lc_bd(self,
                                      model:"mip.Model")-> mip.ConstrList:    
        
        raise NotImplementedError('WIP')
        # major constraint sets definition  
        t_aux_model = mip.Model(name='t_auxiliary_model')
        iis_aux_model = mip.Model(name='t_auxiliary_model')

        linear_constraints = mip.ConstrList(model = t_aux_model) # all the linear model constraints
        variable_bound_constraints = mip.ConstrList(model = t_aux_model) # all the linear model constrants related specifically for the variable bounds
        integer_varlist_crt =  mip.VarList(model = t_aux_model) # the nature vars constraints for vartype in Integer/Binary 
        
        # fill the above sets with the constraints
        for crt in model.constrs:
            linear_constraints.add(crt.expr, name=crt.name)
        for var in model.vars:
            if var.lb != - mip.INF:
                variable_bound_constraints.add(var >= var.lb ,name = '{}_lb_crt'.format(var.name))
            if var.ub != mip.INF:
                variable_bound_constraints.add(var <= var.ub ,name = '{}_ub_crt'.format(var.name))
        for var in model.vars:
            if var.var_type in (mip.INTEGER, mip.BINARY):
                integer_varlist_crt.add(var)
        
        status = 'IIS'
        # add all LC,BD to the incumbent, T= LC + BD
        for var in model.vars: # add all variables as if they where CONTINUOUS and without bonds (because this will be separated)              
            iis_aux_model.add_var(name=var.name, 
                                  lb = -mip.INF,
                                  ub = mip.INF, 
                                  var_type=mip.CONTINUOUS
                                 )
        for crt in  linear_constraints + variable_bound_constraints:
            iis_aux_model.add_constr(crt.expr, name=crt.name)
         
        iis_aux_model.optimize()
        if iis_aux_model.status ==  mip.OptimizationStatus.INFEASIBLE:
            # if infeasible means that this is a particular version of an LP
            return(self.deletion_filter(model)) # (STEP 2)
        
        # add all the integer constraints to the model
        iis_aux_model.vars.remove([var for var in integer_varlist_crt]) # remove all integer variables
        for var in integer_varlist_crt:
            iis_aux_model.add_var(name=var.name, 
                                  lb = -mip.INF,
                                  ub = mip.INF, 
                                  var_type=var.var_type # this will add the var with his original type
                                 )   
        # filter IR constraints that create infeasibility (STEP 1)
        for var in integer_varlist_crt:
            iis_aux_model.vars.remove(iis_aux_model.var_by_name(var.name))
            iis_aux_model.add_var(name=var.name, 
                        lb = -mip.INF,
                        ub = mip.INF, 
                        var_type=mip.CONTINUOUS # relax the integer constraint over var 
                        )   
            iis_aux_model.optimize()
            # if infeasible then update incumbent T = T-{ir_var_crt}
            # else continue 
        # STEP 2 filter lc constraints 
        # STEP 3 filter BD constraints 
        # return IS o IIS
         

    def deletion_filter_milp_lc_ir_bd(self,
                                      model:"mip.Model")-> mip.ConstrList:    
        # TODO
        raise NotImplementedError

class ConstraintPriority(Enum):
    # constraints levels
    VERY_LOW_PRIORITY = 7
    LOW_PRIORITY = 6
    NORMAL_PRIORITY = 5
    MID_PRIORITY = 4
    HIGH_PRIORITY = 3
    VERY_HIGH_PRIORITY = 2
    MANDATORY = 1 

class ConflictResolver():
    
    # mapper for constraint naming (while the attribute 'crt_importance' not in the mip.Constraint class)
    PRIORITY_MAPPER = {
        '_l7':ConstraintPriority.VERY_LOW_PRIORITY,
        '_l6':ConstraintPriority.LOW_PRIORITY,
        '_l5':ConstraintPriority.NORMAL_PRIORITY,
        '_l4':ConstraintPriority.MID_PRIORITY,
        '_l3':ConstraintPriority.HIGH_PRIORITY,
        '_l2':ConstraintPriority.VERY_HIGH_PRIORITY,
        '_l1':ConstraintPriority.MANDATORY
    }

    def __init__(self):
        pass
    
    @classmethod
    def hierarchy_relaxer(cls, 
                          model:mip.Model, 
                          relaxer_objective:str = 'min_abs_slack_val', 
                          default_priority:ConstraintPriority = ConstraintPriority.MANDATORY ) -> mip.Model:
    
        # check if infeasible 
        assert model.status == mip.OptimizationStatus.INFEASIBLE, 'model is not infeasible'
        
        # 0 map priorities 
        crt_priority_dict = cls.map_constraint_priorities(model, default_priority = default_priority)

        cf = ConflictFinder()
        while True:
            # 1. find iis 
            iis = cf.find_iis(model, "additive-algorithm")
            
            iis_priority_mapping = { crt.name :crt_priority_dict[crt.name] for crt in iis}
            # check if "relaxable" model mapping 
            if set(iis_priority_mapping.values()) == set([ConstraintPriority.MANDATORY]):
                raise Exception('Infeasible model, is not possible to relax MANDATORY constraints')
            
            # 2. relax iss 
            slack_dict = cls.relax_iss(iis, 
            iis_priority_mapping, 
            relaxer_objective = relaxer_objective)


        # add the slack variables to the original problem 
        # goto 1 
    
    @classmethod
    def map_constraint_priorities(cls, model:mip.Model, mapper:dict = PRIORITY_MAPPER, default_priority:ConstraintPriority = ConstraintPriority.MANDATORY ) -> dict:
        
        crt_importance_dict = {} # dict with name
        crt_name_list = [crt.name for crt in model.constrs]
        
        #check unique names 
        assert len(crt_name_list) == len(set(crt_name_list)), 'names in constraints must be unique to use conflict refiner, please rename them'

        # TODO: this could be optimized
        for crt_name in crt_name_list:
            for key in mapper.keys():
                if key in crt_name:
                    crt_importance_dict[crt_name] = mapper[key]
                    break
            
        non_defined_crt = [crt_name for crt_name in crt_name_list if crt_name not in  crt_importance_dict.keys()]
        for crt_name in non_defined_crt:
            crt_importance_dict[crt_name] = default_priority

        return crt_importance_dict

    @classmethod 
    def relax_iss(cls, iis:mip.ConstrList, iis_priority_mapping:dict, relaxer_objective:str = 'min_abs_slack_val' ) -> dict:
        raise NotImplementedError




def build_infeasible_cont_model(num_constraints:int = 10, 
                                num_infeasible_sets:int = 20) -> mip.Model:
    # build an infeasible model, based on many redundant constraints 
    mdl = mip.Model(name='infeasible_model_continuous')
    var = mdl.add_var(name='var', var_type=mip.CONTINUOUS, lb=-1000, ub=1000)
    
    
    for idx,rand_constraint in enumerate(np.linspace(1,1000,num_constraints)):
        crt = mdl.add_constr(var>=rand_constraint, name='lower_bound_{0}_l{1}'.format(idx,random.randint(2,7) ))
        logger.debug('added {} to the model'.format(crt))
    
    num_constraint_inf = int(num_infeasible_sets/num_constraints)
    for idx,rand_constraint in enumerate(np.linspace(-1000,-1,num_constraint_inf)):
        crt = mdl.add_constr(var<=rand_constraint, name='upper_bound_{0}_l{1}'.format(idx, random.randint(2,7)))
        logger.debug('added {} to the model'.format(crt))
        
    mdl.emphasis = 1 # feasibility
    mdl.preprocess = 1 # -1  automatic, 0  off, 1  on.
    # mdl.pump_passes TODO configure to feasibility emphasis 
    return mdl


if __name__ == "__main__":
    
    # logger config
    handler = logging.StreamHandler(sys.stdout)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    
    # model experiment
    model = build_infeasible_cont_model()
    logger.debug(model.status)
    model.optimize()
    logger.debug(model.status)

    cf = ConflictFinder()
    iis = cf.find_iis(model, "additive-algorithm")
    logger.debug([crt.name for crt in iis])

    cr = ConflictResolver()
    cr.hierarchy_relaxer(model)
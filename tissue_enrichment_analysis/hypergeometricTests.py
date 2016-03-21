 # -*- coding: utf-8 -*-
"""
Author: David Angeles
Date: May 26, 2015
Requires Python > 3.5
A script to implement a hypergeometric test
Needs:
A tissue dictionary
A control list of gene names
An experimental list of gene names
"""
import pandas as pd
import numpy as np
from scipy import stats
import os
import sys
from urllib.request import urlopen
import contextlib

#if __name__ != '__main__':
#    import matplotlib.pyplot as plt
#    import seaborn as sns
#    sns.set_context('paper')
#    sns.set_style('whitegrid')
#    sns.despine(left= True)
#    sns.despine(trim= True)




def pass_list(user_provided, tissue_dictionary):
    """
    A function to check which genes are in the 
    provided list of user provided names and to
    return a dataframe of presence or fail
    
    Takes two vectors, user_provided and tissue_dictionary in that order
    tissue_dictionary is a pandas dataframe that you should know about
    user_provided is a list of gene names
    """
    length= tissue_dictionary.shape[0] #how many genes in the dict
    
    #make an empty dataframe
    present= pd.DataFrame(index= range(length), columns= ['wbid','provided'])
    
    #fill wbid column with all the gene names
    present.wbid= tissue_dictionary.wbid
    
    #go through and pass attendance -- 1 if present, 0 otherwise
    for item in user_provided:
        present.provided[present.wbid==item]= 1
        
    #remove NA's and make them 0
    present.provided= present.provided.fillna(0)
    
    #return df
    return present
    
#==============================================================================
#hgf is short for hypergeometric function
#==============================================================================
def hgf(gene_list, tissue_df):
    """
    Given a list of tissues and a gene-tissue dictionary,
    returns a p-dictionary for the enrichment of every tissue
    (a p-dictionary is a vector of length equal to the number
    of tissues in the tissue_dictionary, sorted by value)
    
    The entries of the p-vector are p-values not corrected
    for multiple hypothesis testing. 
    
    gene_list should be a list or list-like
    tissue_dictionary should be a pandas df
    """    
    #figure out what genes are in the user provided list
    present= pass_list(gene_list, tissue_df)  
    
    unused= present[present.provided == 0].wbid
    
    #slice out only the genes that were present from the user-provided list    
    wanted= present.wbid[present.provided==1]

    #re-index the dictionary s.t. the wbid is the index
    tissue_df= tissue_df.set_index('wbid')
    
    #number of tissues in the dictionary
    sums_of_tissues= tissue_df.sum()[1:] #this object can be identified by 
    #the column names of tissues and excludes gene IDs
    
    #total size of the urn
    total_genes= tissue_df.shape[0] #total genes in the dictionary

    #slice out the rows from tissue_dictionary that came from the user-provided list
    wanted_dictionary= tissue_df.loc[wanted]
    
    #get the total number of labels from each tissue
    wanted_sum= wanted_dictionary.sum()
    
    #get the total number of genes provided by the user that are in the dictionary
    total= wanted.shape[0]    
    
    #make a hash with the p-values for enrichment of each tissue. 
    p_hash= {}
    exp_hash= {} #expected number for each tissue
    for i, name in enumerate(tissue_df.columns.values[1:]): 
        #if the total number of genes is zero, return p= 1 for all tissues
        if total == 0:
            p_hash[name]= 1
        else:
            #if a certain tissue has never been called, don't test it
            #in certain pathological cases where the list size is small
            #ie. close to 1, probability of never drawing a given label
            #can be close to 1, so survival function can be less than 0.05
            #although the math is right, this behaviour is clearly undesirable
            if wanted_sum[name] == 0:
                p_hash[name]= 1
            else:
                
                #no. of balls of color name picked
                #total number of balls in urn
                #total number of balls of color name in urn
                #total number of balls picked out
                n_obs= wanted_sum[name]
                t_dict= total_genes
                s_tissue= sums_of_tissues[name]
                t_picked= total
#                print(n_obs,t_dict,s_tissue,t_picked)
                p_hash[name]= stats.hypergeom.sf(n_obs,t_dict,s_tissue,t_picked)
                
                exp_hash[name]= stats.hypergeom.mean(t_dict,s_tissue,t_picked)
                
#                if RuntimeWarning:
#                    print('w')
#                    print(n_obs,t_dict,s_tissue,t_picked)
#            
                    
    #return the p-values, the genes associated with each tissue and the user
    #provided genes associate with each tissue. 
    return p_hash, exp_hash, wanted_dictionary, unused
    
    
#==============================================================================
#     
#==============================================================================
def benjamin_hochberg_stepup(p_vals):
    """
    Given a list of p-values, apply a BH
    FDR correction and return the pertaining q values
    
    alpha is a scalar FDR value
    p_vals should be iterable
    """
    #sort the p_values, but keep the index listed
    index= [i[0] for i in sorted(enumerate(p_vals), key=lambda x:x[1])]
    
    #keep the p_values sorted
    p_vals= sorted(p_vals)
    q_vals= [None]*len(p_vals) #initialize an empty list
    prev_q= 0
    
    #BH Step Up begins here. 
    for i, p in enumerate(p_vals):
        q= len(p_vals)/(i+1)*p #calculate the q_value for the current point
        q= min(q, 1) #if q >1, make it == 1
        q= max(q, prev_q) #preserve monotonicity
        q_vals[i]= q #store the q_value
        prev_q= q #update the previous q_value
        
    #return q_vals and the index so we can match up each 
    #q_value with its appropriate tissue. 
    return q_vals, index
    
    
#==============================================================================
# 
#==============================================================================
def return_enriched_tissues(p_hash, alpha):
    """
    Given a hash of p-values
    (tissue -> p-values)
    apply an FDR correction and
    return the q_values that pass
    significance along with the 
    tissue type. 
    """
    
    #initialize a list, a hash and a counter
    p_values= []
    index_to_tissue= {}
    k= 0
    #go through the p_hash
    for key, value in p_hash.items():
        #place each value in the list
        p_values.append(value)
        #store the hash key in an array at the same k index as the value is in p_values
        index_to_tissue[k]= key
        #add 1 to the index
        k+=1
    
    #apply FDR, using BH stepup procedure
    q_values, index= benjamin_hochberg_stepup(p_values)
    
    #place everything in a hash
    q_hash= {}
    for i, value in enumerate(q_values):
        j= index_to_tissue[index[i]]
        q_hash[j]= value
        
    return q_hash
#==============================================================================
#     
#==============================================================================    
def enrichment_analysis(gene_list, tissue_df, alpha= 0.05, aname= '', save= False, show= True):
    """
    executes a complete enrichment analysis (hypergeometric test, BH correction)
    
    gene_list: a list of non-redundant WBIDs
    tissue_df: as provided by WormBase (use fetch_dictionary)
    alpha: significance threshold, defaults to 0.05
    f: filename for the enrichment analysis
    aname= filename to use to save results
    show= Whether to print results or not. 
    """
    print('Executing script\n')
    
    #always make iterable
    if type(gene_list) in [str]:
        gene_list = [gene_list]
    
    
    #calculat the enrichment
    p_hash, exp_hash, wanted_dic, unused= hgf(gene_list, tissue_df)

    #FDR correct
    q_hash= return_enriched_tissues(p_hash, alpha)
                                
    #write results to a dataframe. 
    columns= ['Tissue', 'Expected', 'Observed', 'Enrichment Fold Change', 'Q value']
    df_final= pd.DataFrame(index=np.arange(len(q_hash)), columns=columns)

    i=0    
    for tissue, qval in q_hash.items():
        if qval < alpha:
            
            expected= exp_hash[tissue]
            observed= wanted_dic[tissue].sum()
            
            df_final['Tissue'].ix[i]= tissue
            df_final['Expected'].ix[i]= expected
            df_final['Observed'].ix[i]= observed
            if expected != 0:
                df_final['Enrichment Fold Change'].ix[i]= observed/expected
            else:
                df_final['Enrichment Fold Change'].ix[i]= np.inf
            df_final['Q value'].ix[i]= qval
            i+=1
            
    df_final.dropna(inplace= True)
    df_final['Expected']= df_final['Expected'].astype(float)    
    df_final['Observed']= df_final['Observed'].astype(float)    
    df_final['Enrichment Fold Change']= df_final['Enrichment Fold Change'].astype(float)    
    df_final['Q value']= df_final['Q value'].astype(float)    
    
    df_final.sort_values('Q value', inplace= True)
    if show:
        if len(df_final) == 0:
            print('Analysis returned no enriched tissues.')
        else:
            print(df_final) #print statement for raymond

    if save:
        df_final.to_csv(aname)
        
    
    return df_final, unused#, p_hash
#==============================================================================
#     
#==============================================================================

def plot_enrichment_results(df, y= 'Enrichment Fold Change', title= '', n_bars= 15, 
                            dirGraphs= '', save= True, **kwargs):
    """
    df: dataframe as output by implement_hypergmt_enrichment_tool
    y: One of 'Fold Change', 'Q value' or a user generated column
    n_bars: number of bars to be shown, defaults to 15
    dirGraps: directory to save figures to. if not existent, generates a new folder
    """    
    
    import matplotlib.pyplot as plt
    import seaborn as sns
    sns.set_context('paper')
    sns.set_style('whitegrid')

    if df.empty:
        print('dataframe is empty!')
        return
        
    ax= kwargs.pop('ax', None)
#    
    if ax== None:
        ax= plt.gca()
        
    #sort by q value change
    df.sort_values('Q value', ascending= True, inplace= True)
    #plot first n_bars
    ax= sns.barplot(x= df[y][:n_bars], y= df['Tissue'][:n_bars], ax= ax)    
    
    #fix the plot to prettify it
    ax.set_ylabel('Tissue', fontsize= 15)
    ax.set_xlabel(y, fontsize= 15)
    ax.tick_params(axis= 'x', labelsize= 11)
    ax.tick_params(axis= 'y', labelsize= 11)
    plt.tight_layout()
    
    #save
    if save:
        if dirGraphs:
            if not os.path.exists(dirGraphs):
                os.makedirs(dirGraphs)
            if dirGraphs[len(dirGraphs)-1] != '/':
                plt.savefig(dirGraphs+'/{0}.png'\
                                .format(title))
            else:
                plt.savefig(dirGraphs+'{0}.png'\
                                .format(title))
        else:
            plt.savefig('{0}.png'.format(title))
    
    return ax
#    plt.show()
#    plt.close()
    
#==============================================================================
# 
#==============================================================================
def fetch_dictionary():
    """
    Fetch the dictionary we want.
    """
    
    url_tissue= 'http://131.215.12.204/~azurebrd/work/tissue_enrichment_tool_hypergeometric_test/dict.20151208'
    try:
        with contextlib.closing(urlopen(url_tissue)) as conn:
            data = pd.read_csv(conn)
            return data
    except:
        print('Cannot fetch dictionary. Please check internet connection.')
        
    
#==============================================================================
#==============================================================================
#==============================================================================
#==============================================================================

#
if __name__ == '__main__':
    
    import re
    
    path= './'
    os.chdir(path)
    
    import argparse
    import matplotlib
    matplotlib.use('Agg')
#    from matplotlib.pylab import * 
    import matplotlib.pyplot as plt
    import seaborn as sns
    sns.set_context('paper')
    sns.set_style('whitegrid')
#    sns.despine(left= True)
#    sns.despine(trim= True)

    defQ= 0.1    
    
    parser = argparse.ArgumentParser(description='Run TEA.')
    parser = argparse.ArgumentParser()
    parser.add_argument("tissue_dictionary", help= 'The full path to the tissue dictionary provided by WormBase')
    parser.add_argument("gene_list", help= 'The full path to the gene list (WBIDs) you would like to analyse in .csv format')
    parser.add_argument('title', help= 'Title for your analysis (shouldn\'t include file extension)', type= str)
    parser.add_argument("-q", help= 'Qvalue threshold for significance. Default is {0} if not provided'.format(defQ), type= float)
    parser.add_argument('-p','--print', help= 'Indicate whether you would like to print results', action= 'store_true')    
    parser.add_argument('-s', "--save", help= 'Indicate whether to save your plot.', action= 'store_true')
    args = parser.parse_args()
    
    tdf_name= args.tissue_dictionary
    gl_name= args.gene_list
    title= args.title
    
    if args.q:   
        q= args.q
    else:
        q= defQ
    
    if args.print:
        prnt= True
    else:
        prnt= False
            
    if args.save:
        save= True
                    
    else:
        save= False
            
    tissue_df= pd.read_csv(tdf_name)
    
    gene_list= []
    with open(gl_name, 'r') as f:
        gene_list= [x.strip() for x in f.readlines()]
    
    df_results, unused= enrichment_analysis(gene_list, tissue_df, alpha= q, show= False)
    
    dfname= title+'.csv'
    df_results.to_csv(dfname, index= False)
    
    if prnt:        
        with open(dfname, 'r') as f:
            printer= f.readlines()
            
        for value in printer:
            value= value.split(',')
            for val in value:
                if re.findall("\d+\.\d+", val):
                    ind= value.index(val)
                    x= float(val)
                    if x < 10**-6:
                        value[ind]= '<10^-6'
                    else:
                        value[ind]= '{0:.2g}'.format(x)

            value= '\t'.join(value)
            print(value)
    
    if save:
        plot_enrichment_results(df_results, title= title, save= save)


    sys.exit()
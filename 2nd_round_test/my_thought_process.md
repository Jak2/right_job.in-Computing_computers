
my thought process : 

individual agents so no need of pipeline pattern --> parallel or individual execution both connected to blackboard 


argument parsing 
requests
for parallel execution --> threadpoolexecutor  from concurrent.futures

llm_call 
log_run
get_latest_ouptut
prompt for 3 agents
 run parallel / individual(run single agent)
blackboard to save ip/op of agents 
import json,sys
p=json.load(sys.stdin)
print(json.dumps({'outcome':'ok','outputs':{'trimmed':p['inputs']['text'].strip(' ')}}))

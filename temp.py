__author__ = 'rbd'

matched_file = open('matched.txt', 'r')
replaced_file = open('replaced.txt', 'r')

matched = [tuple(x.split('\t')) for x in matched_file.read().splitlines()]
replaced = [x.split('\t')[0] for x in replaced_file.read().splitlines()]

matched_file.close()
replaced_file.close()

print matched
print replaced

matched = [(x[0], x[1], 'replaced') if x[1][:-4] in replaced else x for x in matched]
print matched

matched_file = open('matched.txt', 'w')
matched_file.writelines('\t'.join(x)+'\n' for x in matched)
matched_file.close()

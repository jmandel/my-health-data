cd raw
for d in $(ls); do
    mkdir ../$d;
done

for i in `find */*.json`; do echo $i; cat $i | jq '.' > ../$i; done
for i in `find */*.xml`; do echo $i; cat $i | tidy -xml -i > ../$i; done
cd ..

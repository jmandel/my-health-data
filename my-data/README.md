# My personal data

These are some data retrieved by patient-facing API from providers where I've received care. The records include:

* 2018 annual physical exam
* 2019 ankle sprain -- urgent care visit + follow-up physical therapy appointment

# Why?

Finding examples of real-world health record exports is hard. These files can serve as an example for developers who want to undesrtand file formats, variations in data representation and quality.

# Formats

Raw results are in `raw` subdirectories. Pretty-formatted results are generated via:

```sh
cd $date_dir
../format.sh
```
